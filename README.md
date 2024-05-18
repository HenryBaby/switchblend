# switchblend

![Docker Image Version](https://img.shields.io/docker/v/henrybaby/switchblend)
![Docker Pulls](https://img.shields.io/docker/pulls/henrybaby/switchblend)
![Docker Image Size](https://img.shields.io/docker/image-size/henrybaby/switchblend)

I wrote this because I was tired of the process of updating my custom firmware and homebrew packages. Going through the process of getting everything together, unpacking, and making the changes that are tailor-made to my specific needs felt kind of meh to me, so I was looking for an AIO solution, but even then they were never quite what I was looking for. The general idea of this is to add the cfw/homebrew to your sources list, and then define a set of "cleanup" tasks to be done to the files before packaging them.

The files are downloaded to `/downloads/input`, and then extracted/moved to `/downloads/output`, the cleanup tasks (which you can define in the tasks tab following the instructions below) are basically four simple commands to manipulate the files within the output folder. 

The commands are `move`, `rename`, `copy`, `delete`.

You can run the program without a GitHub token, but I highly suggest you get one using the instructions <a href="https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens">here</a>. This is to prevent running into any rate limit issues.

## Table of Contents

- [Features](#features)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
    - [Running Locally](#running-locally)
    - [Running with Docker](#running-with-docker)
      - [Build and run from source](#build-and-run-from-source)
      - [Run the pre-built image](#run-the-pre-built-image-from-docker-hub-using-docker-compose)
- [Configuration](#configuration)
  - [Sources](#sources)
  - [Tasks](#tasks)
- [Task Commands](#task-commands)
- [Usage](#usage)
  - [Web GUI](#web-gui)
  - [Running Downloads](#running-downloads)
  - [Running Cleanup](#running-cleanup)
  - [Running Package](#running-package)
- [Roadmap](#roadmap)

## Features

- **Download Management**: Initiate the download of files from configured GitHub sources.
- **Cleanup Management**: Perform post-download tasks on the files.
- **Packaging**: Package the downloaded files into a single zip archive.
- **Scheduler**: Automatically check for updates since the source was added.

## Getting Started

### Prerequisites

- Python 3.11
- Docker
- Docker Compose

### Installation

#### Running Locally

1. Clone the repository:

    ```sh
    git clone https://github.com/HenryBaby/switchblend.git
    cd switchblend
    ```

2. Create a virtual environment and install dependencies:

    ```sh
    python -m venv venv
    source venv/bin/activate  # on Windows use `venv\Scripts\activate`
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

5. Access the application at `http://localhost:5000`.

#### Running with Docker

#### Build and run from source
1. Clone the repository:

    ```sh
    git clone https://github.com/HenryBaby/switchblend.git
    cd switchblend
    ```

2. Create a `.env` file in the root directory and add your environment variables:

    ```env
    TZ=your_timezone (i.e Europe/Stockholm)
    GITHUB_TOKEN=your_github_token
    ```

3. Build and run the Docker container using Docker Compose:

    ```sh
    docker compose up -d
    ```

4. Access the application at `http://docker_host_ip:5000`.

#### Run the pre-built image from Docker Hub using Docker Compose
Create a file named `docker-compose.yml` and another file named `.env` with the following content:

* docker-compose.yml:

    ```
    volumes:
    switchblend:
        name: switchblend

    services:
    switchblend:
        image: henrybaby/switchblend:latest
        container_name: switchblend
        hostname: switchblend
        environment:
        - TZ=${TZ}
        - GITHUB_TOKEN=${GITHUB_TOKEN}
        ports:
        - 5000:5000
        volumes:
        - switchblend:/downloads:rw
        restart: unless-stopped
    ```

* .env:

    ```env
    TZ=your_timezone (i.e Europe/Stockholm)
    GITHUB_TOKEN=your_github_token
    ```

### Configuration

#### Sources

Manage sources by adding or removing GitHub URLs. This can be done through the **Sources** page in the web interface.

1. Navigate to the **Sources** page.
2. Add a new source by providing the project name and GitHub API URL, it should be specified like so:
```
https://api.github.com/repos/USER_NAME/REPO_NAME/releases?per_page=1&sort=created&order=desc
```
3. Delete a source by clicking the delete button next to the source entry.

#### Tasks

Manage tasks for file operations such as delete, move, copy, and rename.

1. Navigate to the **Tasks** page.
2. Add a new task by selecting the command and specifying the source and destination paths. The source path `/downloads/input` is already hardcoded into the program.
3. Delete a task by clicking the delete button next to the task entry.

### Task Commands

Each task consists of a command and source and destination paths. The following commands are available:

1. `delete`: Deletes the specified file or directory.

    ```sh
    delete file_or_directory
    ```

2. `move`: Moves the specified file or directory to a new location.

    ```sh
    move file_or_directory /path/to/destination
    ```

3. `copy`: Copies the specified file or directory to a new location.

    ```sh
    copy file_or_directory /path/to/destination
    ```

4. `rename`: Renames the specified file or directory.

    ```sh
    rename file_or_directory /path/to/new_name
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

## Roadmap
Planned feature, in no particular order.
 - [x] Support for uploading directly to switch.
 - [ ] Support for other sources than just GitHub API (currently does support .zip file downloads directly but it's a bit wonky, so stay away from it until a proper release).
 - [ ] Extend some of the functionality to env parameters, like the update scanner interval.
 - [x] Profile-based management (switch specific sources/tasks.json for people with multiple switch units).
 - [ ] Multi-arch docker image: (Currently only supports `linux/arm64`).
