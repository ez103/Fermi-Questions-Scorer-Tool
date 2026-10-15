from pathlib import Path
import csv
import hashlib
import io
import json
import sqlite3
import pandas as pd
import streamlit as st
from core import assess, delete_record, division, integer, records, regrade_records, save_record, update_record_answers
from imaging import LAYOUT_PRESETS, align_corners, answers, image_url, load_page, preview, region

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title='Fermi Grader', page_icon='📝', layout='wide')
st.title('Fermi Grader')
st.caption('Local handwriting recognition · editable answers · separate B and C divisions')

@st.cache_resource
def reader(engine='TrOCR Small'):
    if engine == 'PaddleOCR (trial)':
        from paddle_recognition import PaddleReader
        return PaddleReader()
    from recognition import Reader
    return Reader()


def csv_bytes(rows):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode('utf-8-sig')

with st.sidebar:
    st.header('Answer key')
    key_file = st.file_uploader('Load key text file', type=['txt'], key='key_upload')
    key_file_error = False
    if key_file:
        contents = key_file.getvalue()
        fingerprint = hashlib.sha256(contents).hexdigest()
        try:
            uploaded_key = contents.decode('utf-8-sig')
            if st.session_state.get('loaded_key_file') != fingerprint:
                st.session_state.key_text = uploaded_key
                st.session_state.loaded_key_file = fingerprint
        except UnicodeDecodeError:
            key_file_error = True
            st.error('The key file must be UTF-8 plain text. Remove it or upload a valid text file.')
    else:
        st.session_state.pop('loaded_key_file', None)
    key_text = st.text_area('60 integers, separated by spaces or commas', height=160, key='key_text')
    try:
        tokens = key_text.replace(',', ' ').split()
        keys = [integer(t) for t in tokens]
        key_ready = not key_file_error and len(keys) == 60 and all(k is not None for k in keys)
    except ValueError:
        keys, key_ready = [], False
    if not key_ready:
        st.info('Enter exactly 60 integer answers to enable grading.')
        keys = [None]*60
    st.caption('A valid answer key automatically updates all saved records in both divisions. Each record keeps its saved scoring rules. Incomplete or invalid keys leave saved scores unchanged.')
    st.header('Scoring rules')
    st.caption('Initial assumption: exact = 5, off by 1 = 3, off by 2 = 1, otherwise = 0. Confirm for your test.')
    awards = tuple(st.number_input(label, min_value=0, max_value=100, value=value, step=1)
                   for label, value in [('Exact answer',5),('Difference of 1',3),('Difference of 2',1)])
    st.caption('Blank answers earn 0. Edits update scores after Enter or leaving the cell.')

grade_tab, saved_tab = st.tabs(['Grade a sheet', 'Saved records'])
for field in ['team_number','team_name']:
    if 'pending_'+field in st.session_state:
        st.session_state[field] = st.session_state.pop('pending_'+field)

with grade_tab:
    team_a, team_b = st.columns(2)
    with team_a:
        team_number = st.text_input('Team number', key='team_number', placeholder='B12 or C12').strip().upper()
        try:
            team_division = division(team_number)
            st.success(f'Division {team_number[0]} · {team_division}')
        except ValueError as exc:
            team_division = None
            st.caption(str(exc))
    with team_b:
        team_name = st.text_input('Team name', key='team_name')
    st.caption('Team fields are editable. Optional header recognition is available below after upload.')
    uploaded = st.file_uploader('Upload a completed sheet', type=['pdf','png','jpg','jpeg'], key='sheet')
    page = st.number_input('PDF answer-page number', min_value=1, value=2, step=1)
    if uploaded:
        try:
            original = load_page(uploaded.getvalue(), uploaded.name, page)
        except Exception as exc:
            st.error(str(exc))
            original = None
        if original:
            with st.expander('Align page and configure answer areas', expanded=True):
                template = st.selectbox('Answer sheet layout', list(LAYOUT_PRESETS), key='layout_template')
                preset = LAYOUT_PRESETS[template]
                st.caption('Red rectangles must enclose handwriting only. Questions run down each column, then continue at the top of the next column. Use a full-page scan, or set the four corners for a phone photo.')
                rectify = st.checkbox('Correct phone-photo perspective')
                corners = []
                if rectify:
                    for label, default in zip(['Top-left','Top-right','Bottom-right','Bottom-left'], [(0.,0.),(1.,0.),(1.,1.),(0.,1.)]):
                        cols = st.columns(2)
                        corners.append(tuple(cols[i].number_input(label+(' X' if i==0 else ' Y'), min_value=0., max_value=1., value=default[i], step=.005, format='%.3f') for i in range(2)))
                try:
                    image = align_corners(original, corners) if rectify else original
                    layout = {'column_x': []}
                    x_cols = st.columns(len(preset['column_x']))
                    for idx, value in enumerate(preset['column_x']):
                        layout['column_x'].append(x_cols[idx].number_input(f'Column {idx+1} X',
                            min_value=0., max_value=1., value=float(value), step=.001, format='%.5f',
                            key=f'layout_{template}_column_{idx}'))
                    config_cols = st.columns(3)
                    for idx, name in enumerate(['width', 'first_y', 'row_step', 'height']):
                        layout[name] = config_cols[idx%3].number_input(name.replace('_',' ').title(),
                            min_value=0., max_value=1., value=float(preset[name]), step=.001, format='%.5f',
                            key=f'layout_{template}_{name}')
                    crops = answers(image, layout)
                    st.image(preview(image,layout), width=800)
                except Exception as exc:
                    st.error(str(exc))
                    crops, image = None, original
                st.download_button('Download layout settings', json.dumps(layout,indent=2), 'layout.json')
            if crops:
                identity = hashlib.sha256(uploaded.getvalue()+json.dumps([page,layout,rectify,corners],sort_keys=True).encode()).hexdigest()
                if st.session_state.get('sheet_id') != identity:
                    st.session_state.sheet_id = identity
                    st.session_state.rows = [{'Question':i+1,'Handwriting':image_url(crop),'Answer':'','Warning':'Not read yet','Reviewed':False} for i,crop in enumerate(crops)]
                    st.session_state.editor_version = st.session_state.get('editor_version',0)+1
                engine = st.selectbox('Handwriting reader', ['PaddleOCR (trial)', 'TrOCR Small'], key='ocr_engine')
                st.caption('PaddleOCR is a local trial. The first read takes longer while the model loads. Switching readers keeps your current answers until you click Read handwriting locally again.')
                integer_only = st.checkbox('Recognize integers only', value=True,
                    help='Accept digits and an optional leading minus sign. PaddleOCR normalizes a space after a minus and flags other non-integer readings for manual entry. TrOCR constrains generated characters. Applies only to answers, not team headers.')
                if st.button('Read handwriting locally', type='primary'):
                    bar = st.progress(0.)
                    try:
                        readings = reader(engine).read(crops, bar.progress, integer_only=integer_only)
                        for row,(text,reason) in zip(st.session_state.rows,readings):
                            row.update(Answer=text,Warning=reason,Reviewed=False)
                        st.session_state.editor_version += 1
                        st.rerun()
                    except Exception as exc:
                        st.error(f'Recognition unavailable: {exc}. You can still type answers manually. See README for model installation.')
                    finally:
                        bar.empty()
                with st.expander('Read team name and number from the page header'):
                    st.caption('The supplied answer page has no team header. For a revised sheet, configure each header crop using page fractions. Always verify the result.')
                    for field in ['team_number','team_name']:
                        cols = st.columns(4)
                        box = tuple(cols[i].number_input(field.replace('_',' ').title()+' '+label, min_value=0.,max_value=1.,value=value,step=.005,key=field+label) for i,(label,value) in enumerate(zip(['X','Y','Width','Height'],[.1,.02,.35,.03])))
                        if st.button('Recognize '+field.replace('_',' '), key='read_'+field):
                            try:
                                text = reader(engine).read([region(image,box)], integer_only=False)[0][0]
                                st.session_state['pending_'+field] = text
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))
                st.subheader('Review answers')
                st.caption('All readings start unreviewed. Check the crop, edit the answer, then check Reviewed. Model warnings are advisory, not guarantees.')
                if st.checkbox('Show only answers needing review'):
                    visible = [row for row in st.session_state.rows if not row['Reviewed']]
                else:
                    visible = st.session_state.rows
                if visible:
                    edited = st.data_editor(pd.DataFrame(visible), hide_index=True, height=650, row_height=60,
                        disabled=['Question','Handwriting','Warning'],
                        column_config={'Handwriting':st.column_config.ImageColumn('Handwriting',width='medium'),
                                       'Answer':st.column_config.TextColumn('Answer',width='small'),
                                       'Reviewed':st.column_config.CheckboxColumn('Reviewed')},
                        key=f'editor_{identity}_{st.session_state.editor_version}_{len(visible)}',width='stretch')
                    edited_rows = edited.to_dict('records')
                    for edited_row in edited_rows:
                        if pd.isna(edited_row['Answer']):
                            edited_row['Answer'] = ''
                    by_question = {int(row['Question']):row for row in edited_rows}
                    for row in st.session_state.rows:
                        if row['Question'] in by_question:
                            row.update(by_question[row['Question']])
                results = assess(st.session_state.rows,keys,awards)
                invalid = [r['question'] for r in results if r['invalid']]
                unreviewed = sum(not r['reviewed'] for r in results)
                score = sum(r['points'] for r in results)
                metrics = st.columns(3)
                metrics[0].metric('Score (provisional)' if unreviewed else 'Score',f'{score} / {60*max(awards)}' if key_ready else 'Key required')
                metrics[1].metric('Needs review',unreviewed)
                metrics[2].metric('Invalid entries',len(invalid))
                if invalid:
                    st.error('Enter integers or blanks for questions: '+', '.join(map(str,invalid)))
                with st.expander('Question-by-question points'):
                    st.dataframe(pd.DataFrame(results),hide_index=True)
                final = st.checkbox('Mark this record final',disabled=bool(unreviewed or invalid or not key_ready))
                record = dict(team_number=team_number,team_name=team_name,division=team_division,
                              score=score,status='Final' if final and not unreviewed and not invalid and key_ready else 'Draft',
                              answer_key=keys,awards=awards,results=results,
                              rows=[{k:v for k,v in row.items() if k!='Handwriting'} for row in st.session_state.rows],
                              layout=layout,source_filename=uploaded.name)
                st.download_button('Export answers and points CSV',csv_bytes(results),'answers.csv')
                if st.button('Save team record', disabled=not(team_division and team_name.strip() and key_ready and not invalid)):
                    record_id = save_record(ROOT/'data'/'grades.sqlite',record)
                    st.success(f'Saved {record["status"].lower()} record #{record_id} for {team_number}.')
    else:
        st.info('Upload a scan or photo to begin. For the supplied PDF, the answers are on page 2.')

with saved_tab:
    if 'edited_record_message' in st.session_state:
        st.success(st.session_state.pop('edited_record_message'))
    if 'deleted_record_message' in st.session_state:
        st.success(st.session_state.pop('deleted_record_message'))
    if key_ready:
        try:
            regraded = regrade_records(ROOT/'data'/'grades.sqlite', keys)
            if regraded:
                st.success(f'Updated {regraded} saved record(s) using the current answer key.')
        except (ValueError, sqlite3.Error) as exc:
            st.error(f'Saved scores could not be updated; the previous saved scores are still shown. {exc}')
    saved = records(ROOT/'data'/'grades.sqlite')
    if not saved:
        st.info('Saved team records will appear here.')
    else:
        which = st.selectbox('Division', ['All','B · Middle school','C · High school'])
        selected = [r for r in saved if which=='All' or r['team_number'].startswith(which[0])]
        flat = [{k:v for k,v in r.items() if k!='record'} for r in selected]
        if flat:
            st.dataframe(pd.DataFrame(flat),hide_index=True)
            st.download_button('Export team scores CSV',csv_bytes(flat),'team_scores.csv')
            selected_id = st.selectbox('Open saved record', [r['id'] for r in selected])
            selected_record = next(r['record'] for r in selected if r['id']==selected_id)
            st.dataframe(pd.DataFrame(selected_record['results']),hide_index=True)
            st.caption('A valid sidebar key recalculates saved scores using each record\'s saved scoring rules. Correct saved answers below; no sheet upload is needed.')
            if selected_record.get('rows'):
                with st.expander('Edit saved answers'):
                    st.write(f'Record #{selected_id} · {selected_record["team_number"]} · {selected_record["team_name"]}')
                    st.caption('Edit the Answer column, then save. Use integers or leave blanks. Saving updates this record and its score; review flags and Draft/Final status stay the same. Original handwriting images are not stored with records.')
                    version = hashlib.sha256(json.dumps(selected_record['rows'], sort_keys=True).encode()).hexdigest()[:16]
                    with st.form(f'edit_saved_record_{selected_id}_{version}'):
                        answer_rows = [{'Question': row['Question'], 'Answer': str(row['Answer']) if row['Answer'] is not None else ''}
                                       for row in sorted(selected_record['rows'], key=lambda row: row['Question'])]
                        corrections = st.data_editor(pd.DataFrame(answer_rows), hide_index=True, height=420,
                            disabled=['Question'], num_rows='fixed',
                            column_config={'Answer': st.column_config.TextColumn('Answer')},
                            key=f'saved_answers_{selected_id}_{version}', width='stretch')
                        save_changes = st.form_submit_button('Save answer changes')
                    if save_changes:
                        answers_by_question = {int(row['Question']): '' if pd.isna(row['Answer']) else row['Answer']
                                               for row in corrections.to_dict('records')}
                        try:
                            updated_score = update_record_answers(ROOT/'data'/'grades.sqlite', selected_id, answers_by_question)
                            st.session_state.edited_record_message = f'Updated answers for record #{selected_id}. New score: {updated_score}.'
                            st.rerun()
                        except (ValueError, sqlite3.Error) as exc:
                            st.error(f'Answers were not saved. {exc}')
            st.download_button('Download complete saved record',json.dumps(selected_record,indent=2),'record.json')
            with st.expander('Delete selected record'):
                st.write(f'Record #{selected_id} · {selected_record["team_number"]} · {selected_record["team_name"]}')
                confirmed = st.checkbox('Permanently delete this saved record', key=f'confirm_delete_{selected_id}')
                if st.button('Delete record', disabled=not confirmed, key=f'delete_record_{selected_id}'):
                    if delete_record(ROOT/'data'/'grades.sqlite', selected_id):
                        st.session_state.deleted_record_message = f'Deleted record #{selected_id} for {selected_record["team_number"]}.'
                        st.rerun()
                    else:
                        st.warning('This record has already been deleted. Refresh to update the list.')
