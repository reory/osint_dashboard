# Contributing to OSINT Username Intelligence Dashboard

First off, thank you for taking the time to contribute!

Please read through the guidelines below to keep the development process clean and efficient.

---

## 🛠️ How Can I Contribute?

### 1. Reporting Bugs
- Check the GitHub Issues tab to ensure the bug hasn't already been reported.
- If it's a new issue, clearly describe the problem, provide steps to reproduce it, and include any relevant stack trace logs (especially encoding issues like `UnicodeDecodeError`).

### 2. Suggesting Enhancements
I welcome ideas and pull requests for:
- 📊 **Data Visualization:** Interactive relationship graphs (e.g., using `vis.js`).
- 👁️ **Biometrics:** Avatar image comparison scripts.
- 🔀 **Multi-Targeting:** Batch username lists or CSV uploads.
- 📄 **Reporting:** Exporting visual dossiers directly to PDF formats.

### 3. Submitting Code Changes
Fork the repository and create your feature branch from `main`:
   ```bash
   git checkout -b feature/amazing-new-feature
   ```

Ensure your code maintains the decoupled architecture:

Heavy CLI background execution belongs in the FastAPI api/ engine.

User interaction, view logic, and data layouts belong in the Django core/ application.

Test your changes locally on Windows to make sure sub-shell piping streams do not choke on character encoding maps.

Commit your changes with clear, concise commit messages:

```Bash
git commit -m "feat: added PDF report generation using WeasyPrint"
```
Push your branch and open a clean Pull Request against our main branch.

---

## 📜 Code Style Guide
Follow standard PEP 8 styling for all Python scripts.

Keep FastAPI and Django endpoints strictly decoupled.

Always include helpful, non-verbose comments on complex lines to keep the workspace accessible for learning developers. 😁