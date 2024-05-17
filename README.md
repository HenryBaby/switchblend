# switchblend

## Overview

**switchblend** is a Flask-based web application designed to manage and automate the downloading, cleanup, and packaging of files, primarily from GitHub sources. It features a scheduler for periodic checks, background task execution, and a user-friendly interface for managing URLs and tasks.

## Features

- **Download Management**: Automate the download of files from configured GitHub sources.
- **Cleanup Management**: Perform various file operations such as delete, move, copy, and rename based on user-defined tasks.
- **Packaging**: Package downloaded files into a zip archive.
- **Scheduler**: Automatically check for updates and perform tasks at regular intervals.
- **User Interface**: Manage sources and tasks through a web interface.

## Getting Started

### Prerequisites

- Python 3.11
- Docker
- Docker Compose

### Installation

#### Running Locally

1. Clone the repository:

    ```sh
    git clone https://github.com/yourusername/switchblend.git
    cd switchblend
    ```

2. Create a virtual environment and install dependencies:

    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

3. Set up environment variables:

    Create a `.env` file in the root directory and add your GitHub token:

    ```env
    GITHUB_TOKEN=your_github_token
    ```

4. Run the Flask application:

    ```sh
    python app.py
    ```

5. Access the application at `http://127.0.0.1:5000`.

#### Running with Docker

1. Clone the repository:

    ```sh
    git clone https://github.com/yourusername/switchblend.git
    cd switchblend
    ```

2. Create a `.env` file in the root directory and add your environment variables:

    ```env
    TZ=your_timezone
    GITHUB_TOKEN=your_github_token
    ```

3. Build and run the Docker container using Docker Compose:

    ```sh
    docker-compose up -d
    ```

4. Access the application at `http://127.0.0.1:5000`.

### Configuration

#### Sources

Manage sources by adding or removing GitHub URLs. This can be done through the **Sources** page in the web interface.

1. Navigate to the **Sources** page.
2. Add a new source by providing the project name and GitHub API URL.
3. Delete a source by clicking the delete button next to the source entry.

#### Tasks

Manage tasks for file operations such as delete, move, copy, and rename.

1. Navigate to the **Tasks** page.
2. Add a new task by selecting the command and specifying the source and destination paths.
3. Delete a task by clicking the delete button next to the task entry.

### Task Commands

Each task consists of a command and source and destination paths. The following commands are available:

1. **delete**: Deletes the specified file or directory.
    - **Source**: The path to the file or directory to delete.
    - **Destination**: Not required for this command.

    Example:
    ```sh
    delete /path/to/file_or_directory
    ```

2. **move**: Moves the specified file or directory to a new location.
    - **Source**: The path to the file or directory to move.
    - **Destination**: The new path for the file or directory.

    Example:
    ```sh
    move /path/to/source /path/to/destination
    ```

3. **copy**: Copies the specified file or directory to a new location.
    - **Source**: The path to the file or directory to copy.
    - **Destination**: The new path for the file or directory.

    Example:
    ```sh
    copy /path/to/source /path/to/destination
    ```

4. **rename**: Renames the specified file or directory.
    - **Source**: The path to the file or directory to rename.
    - **Destination**: The new name for the file or directory.

    Example:
    ```sh
    rename /path/to/source /path/to/new_name
    ```

### Usage

#### Web GUI

The web gui displays the list of added sources, their last updated times, and indicates if any updates are available.

#### Running Downloads

Trigger the download process manually by clicking the **Download** button in the navigation bar. This will download files from the configured sources and reset the update status.

#### Running Cleanup

Trigger the cleanup process manually by clicking the **Cleanup** button in the navigation bar. You can also choose to clear the input directory by checking the corresponding checkbox before running the cleanup.

#### Running Package

Trigger the packaging process manually by clicking the **Package** button in the navigation bar. This will package the contents of the `downloads/output/` directory into a zip archive.

## Project Structure
