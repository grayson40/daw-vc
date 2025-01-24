# DAW Version Control Diff Tool

A Python tool for parsing and diffing changes in FL Studio project files (.flp).

## Table of Contents

- [Description](#description)
- [Installation](#installation)
- [Testing](#testing)

## Description

DAW Version Control Diff Tool is designed to parse FL Studio project files and identify changes between different versions. It leverages the `pyflp` library to read and extract metadata from FL Studio projects, enabling users to track modifications effectively.

## Installation

Use `pip` to install the required dependencies.

1. Clone the repository:
   ```bash
   git clone https://github.com/grayson40/daw-diff-tool.git
   cd daw-diff-tool
   ```

2. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Testing

To run the tests for this project, you can use `pytest`. Make sure you have installed the dependencies first.

1. Run the tests:
   ```bash
   pytest
   ```

The tests are located in the `tests` directory and cover various scenarios, including loading valid projects, handling invalid files, and testing exception handling.

> **Note:** This repository is private and intended for personal use and development. Please do not share or distribute without permission.
