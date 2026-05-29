# LeadHarvest

LeadHarvest is a Google Maps lead generation and data extraction project built with Python.

The repository intentionally contains two versions of the same project:

* **v1** -> Original command-line prototype
* **v2** -> Expanded application with a backend API, frontend interface, job management, exports, and improved project structure

The purpose of keeping both versions is to document the project's evolution rather than only showcasing the final result.

---

## Project Journey

### Version 1 - Prototype

The first version focused on solving a single problem:

> Can I automatically collect business leads from Google Maps and export them into a usable format?

This version was built as a command-line application using Python and Playwright.

Key characteristics:

* Single-file approach
* Direct browser automation
* Excel export
* Minimal architecture
* Built to validate the idea quickly

---

### Version 2 - Application

After the prototype proved successful, the project was redesigned into a more structured application.

Version 2 introduces:

* Backend API architecture
* Frontend user interface
* Job-based scraping workflow
* Export management
* Logging system
* Better separation of concerns
* Improved maintainability

Instead of focusing solely on scraping, the second version focuses on creating a more complete user experience.

---

## Repository Structure

```text
leadharvest/
│
├── v1/
│   └── Initial prototype
│
└── v2/
    ├── Backend API
    ├── Frontend Interface
    ├── Export System
    ├── Logging
    └── Job Management
```

---

## Technologies Used

* Python
* Playwright
* FastAPI
* OpenPyXL
* HTML
* CSS
* JavaScript

---

## What I Learned

This project helped me gain practical experience with:

* Browser automation
* Dynamic web scraping
* Project architecture
* API development
* Frontend-backend communication
* Logging and monitoring
* Refactoring prototypes into maintainable applications

One of the most valuable lessons was understanding that building software is often an iterative process. The first version solved the problem. The second version focused on solving it better.

---

## Running the Project

Each version contains its own setup instructions and documentation.

* See `v1/README.md` for the prototype version.
* See `v2/README.md` for the application version.

---

## Project Status

Active learning project.

This repository is intended to showcase both the development process and the technical progression from an initial proof of concept to a more structured application.
