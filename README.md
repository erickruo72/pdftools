# TapToPDF – All-in-One PDF Tools

> Personal project powering [TapToPDF.com](https://taptopdf.com), a free, user-friendly platform for managing PDF files. Built with Flask and modern web technologies, TapToPDF offers fast and secure PDF editing tools similar to iLovePDF and SmallPDF.

---

## Features

* 📄 **Merge PDFs** – Combine multiple files into one
* ✂️ **Split PDFs** – Extract or divide pages easily
* 📉 **Compress PDFs** – Reduce file size while maintaining quality
* 🔄 **Convert PDFs** – PDF ⇆ Word, Excel, PowerPoint, Images
* 📝 **Edit PDFs** – Add text, annotations, and basic changes
* 🔐 **Protect PDFs** – Add password protection
* 🔓 **Unlock PDFs** – Remove passwords (if permitted)
* 💧 **Watermark PDFs** – Add custom text or image watermarks
* 🔢 **Page Numbers** – Insert automatic page numbering
* ✏️ **Crop PDFs** – Select and crop specific areas

---

## Tech Stack

* **Backend**: Python (Flask)
* **Frontend**: HTML, CSS, JavaScript (with drag-and-drop UI)
* **Libraries**: PyPDF2, pdfplumber, Pillow, ReportLab, and others for PDF processing
* **Hosting**: Nginx + Gunicorn on Ubuntu server

---

## Installation (Development)

1. Clone the repo:

   ```bash
   git clone https://github.com/erickruo72/pdftools.git
   cd pdftools
   ```

2. Create and activate virtual environment:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Run the Flask app:

   ```bash
   flask run
   ```

App will be available at `http://127.0.0.1:5000`

---

## Usage

* Upload one or more PDF files
* Choose the desired action (merge, split, compress, convert, etc.)
* Preview results (where available)
* Download processed PDF instantly

---

## Roadmap / To-Do

* [ ] Add advanced editing tools (highlight, draw)
* [ ] Cloud storage integration (Google Drive, Dropbox)
* [ ] Batch processing
* [ ] Dark mode UI

---

## License

This project is **private** and maintained as part of the TapToPDF.com platform. Not for redistribution without permission.

---

🔗 **Live site**: [https://taptopdf.com](https://taptopdf.com)
