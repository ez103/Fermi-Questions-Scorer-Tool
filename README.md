# Fermi Questions Scorer Tool

Upload a 60-answer sheet, read handwriting locally, review cropped answers, and grade against a key. The default layout matches the 2026 UT Invitational answer page: **four columns of 15**, numbered down each column (1–15, 16–30, 31–45, 46–60). The original two-column layout is also available. Team numbers beginning B mean middle school; C means high school. Team names and numbers are editable, with optional header OCR. No paid API calls; the grading app loads recognition weights locally only.

## Windows setup

Use Python 3.11 or 3.12 (64-bit). Extract this entire folder, then open Command Prompt in it:

```
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python download_model.py
```

If you have Python 3.11, replace `-3.12` with `-3.11`. Installation and model download require internet, several GB of disk space, and may take time. Afterwards double-click `Start_Windows.bat`, or run:

```
.venv\Scripts\python -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

The interface opens in your browser, but processing runs on your computer. Keep the terminal open. A GPU is optional; CPU recognition will be slower.

macOS/Linux: create a venv with `python3 -m venv .venv`, use `.venv/bin/python` for the same pip, download, and streamlit commands.

## Use

### Try PaddleOCR

On Windows, run `Setup_PaddleOCR.bat` once after the standard app setup. It installs
PaddleOCR in a separate `.venv-paddle` environment and downloads the pinned
`en_PP-OCRv5_mobile_rec` model. Start the app normally with `Start_Windows.bat`.
After uploading a sheet, choose **PaddleOCR (trial)** under **Handwriting reader**
and click **Read handwriting locally**. TrOCR Small remains available in that menu.
Switching the menu alone preserves current answers; clicking Read replaces them.

PaddleOCR trims empty crop margins and reads batches on the CPU. Its process stays
loaded for subsequent reads; the first read includes startup time. It processes
images locally, without a cloud OCR service. Integer mode accepts signed digits,
normalizes a Unicode minus and spaces immediately after it, and flags other output
for manual entry. It does not turn `O` into `0`, join separated numbers, or remove
decimal points to force a guess. Blank or faint crops still require review.

Development trial: the supplied font-generated 60-answer sample scored 60/60
after margin trimming, taking approximately 1.1 seconds for recognition with CPU
acceleration, excluding model startup. Without trimming it scored 56/60. This is
a synthetic-font check, not a real-handwriting accuracy estimate. Real sheets
must still be reviewed. The model receives no answer key.

macOS/Linux setup: `python3 -m venv .venv-paddle`, then
`.venv-paddle/bin/python -m pip install -r requirements-paddle.txt`, followed by
`.venv/bin/python download_paddle_model.py`. These platforms have not been tested.

### Grading and records

1. Paste exactly 60 answer-key integers, or upload a UTF-8 plain text file containing them separated by whitespace or commas. Uploaded keys appear in the text box and can be edited there. When a valid key is committed (click outside the text box or press Ctrl+Enter), **all saved records in both divisions automatically recalculate**. Incomplete or invalid keys leave saved scores unchanged.
2. Confirm the scoring rules. Defaults are an **unconfirmed assumption**: exact 5, difference 1 gives 3, difference 2 gives 1; all other answers and blanks give 0. Change points in the sidebar.
3. Enter team number (B or C followed by digits) and team name.
4. Upload a PDF or image. The supplied sample's answer page is page 2; use page 1 for a one-page PDF.
5. Under **Align page and configure answer areas**, select **2026 UT Invitational (4 columns of 15)** for the new answer sheet, or **Original sheet (2 columns of 30)** for earlier sheets. Verify all 60 red crop rectangles. The new preset was measured from page 2 and covers the space above each answer line, excluding the printed rule and question number. Coordinates are fractions of the full page. Adjust each column's X position, first Y, row spacing, width and height if the scan shifts. Changing the layout resets the current unsaved answer review, so configure it before reading handwriting. Phone photos can be corrected by setting the four page corners clockwise, using fractions of image width/height. The target ratio assumes US Letter.
6. Choose the handwriting reader and click Read handwriting locally. **Recognize integers only** is enabled by default: TrOCR constrains generated characters; PaddleOCR validates its output as described above. Blank readings remain possible. Turn it off for unrestricted recognition; team-header recognition is always unrestricted. This limits the output format, not recognition errors, and has no access to the answer key. Inspect EVERY answer, correct readings, and check Reviewed. Filter to unreviewed items if helpful. Leaving blanks and marking them reviewed confirms that they are genuinely blank.
7. Scores update when edits are committed (Enter or leave the cell), without rerunning OCR. Final status requires a complete key, valid integers, and review of all answers.
8. Save records and export CSV. Drafts can be saved. Another Save creates a new record rather than overwriting a team. Saved answers, review flags and Draft/Final status are preserved, while each valid new sidebar key updates the saved answer keys, question-by-question points and totals in the database. Recalculation uses each record's saved scoring rules; changing sidebar points only affects the sheet currently being graded and future saves. Tables and new CSV/JSON exports reflect the updated scores; previously downloaded files do not change. No scan upload or OCR rerun is needed. The records table includes record IDs/status so duplicates remain visible. Separate division filters are available. The app uses one shared answer key for all saved records, so keep different tests in separate databases.
9. To remove a test or duplicate entry, select it under **Saved records → Open saved record**, expand **Delete selected record**, verify its ID and team, check **Permanently delete this saved record**, and click **Delete record**. Only that snapshot is deleted; other records for the same team remain. Deletion cannot be undone in the app. Download the complete record first if you want a copy.
10. To correct saved answers, select the record and expand **Edit saved answers**. Edit the Answer column (integers or blanks), then click **Save answer changes**. This updates the existing record, recalculates its question points and total using its saved key and scoring rules, and refreshes the table and new exports. A valid sidebar key is applied before recalculation; with no valid sidebar key, the record's last saved key is used. Review flags and Draft/Final status are preserved. Invalid edits are rejected without changing the saved record. No scan upload or OCR rerun is needed; original handwriting images are not stored with records.

## Header fields

The supplied page-2 template has no team-name/number header. Enter those manually or configure header crop rectangles for your revised template. Optional header OCR uses the same model, requires verification, and does not identify header locations automatically. Adding a header may shift answer positions: recalibrate the answer crops.

## Data and limitations

- SQLite records are stored in `data/grades.sqlite` next to the app. Back up that file. Uploaded images and crops are held in the current browser session, not saved with records. Keep original scans separately.
- Local recognition offers PaddleOCR's English PP-OCRv5 mobile recognizer and Microsoft TrOCR small handwritten. Neither has been validated on real completed competition sheets. Cross-outs, touching digits, minus signs, pencil and underlines can cause mistakes.
- All OCR results begin unreviewed. Warnings based on model output are advisory; they are not calibrated probabilities and cannot guarantee that errors are detected. Blank recognition is not automatically trusted.
- Image alignment and crop bounds are validated, but you must inspect the overlay. Partial scans, arbitrary layouts and poor lighting are not automatically repaired.
- Team number format currently requires B/C plus digits. Team metadata must be confirmed by the reviewer.
- Downloaded models and Python dependencies are not bundled in the ZIP. You can launch and manually enter/review answers before installing recognition dependencies if Streamlit, Pillow, pandas, NumPy and PyMuPDF are installed.
- Header OCR, actual OCR accuracy and photo alignment require testing on completed sheets. This is a local prototype, not a validated competition grading system.

## Development checks

The repository includes the app, tests, setup scripts and Streamlit configuration. Virtual environments, downloaded model weights, saved grades, secrets and local test artifacts are excluded. Use `download_model.py` to obtain the model after installation. Competition PDFs and completed scans are not bundled.

```
python -m unittest discover -s tests -v
```

App: `app.py`; scoring/storage: `core.py`; image handling: `imaging.py`; recognition: `recognition.py`. No cloud services or API keys are used.
