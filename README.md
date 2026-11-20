# Griffin 🦅

**A personal AI desktop assistant inspired by JARVIS.**

Griffin combines a Python desktop application, a local Windows bridge,
and n8n workflows to connect voice interaction with useful desktop
actions. It is an experimental, self-hosted project intended to be
customized and extended.

> **Project status:** Early development. The repository contains the
> Python desktop client and local bridge. Your n8n workflows and
> PostgreSQL database are configured separately.

## Contents

-   [What Griffin can do](#what-griffin-can-do)
-   [Highlights](#highlights)
-   [Architecture](#architecture)
-   [Requirements](#requirements)
-   [Setup](#setup)
-   [PostgreSQL and long-term memory
    setup](#postgresql-and-long-term-memory-setup)
-   [Run Griffin](#run-griffin)
-   [Current limitations](#current-limitations)
-   [Ideas you can add](#ideas-you-can-add)
-   [Security notes](#security-notes)
-   [Project structure](#project-structure)

## What Griffin can do

The current project includes:

-   **Voice interaction:** Capture microphone audio and send it to an
    n8n voice workflow. The workflow can return a transcript, an
    assistant response, and generated speech audio.
-   **Desktop interface:** A Python GUI for interacting with Griffin.
-   **Local computer actions:** Use the Windows bridge to open and close
    supported applications and check whether an application is running.
-   **Workspace file operations:** List workspace files, create folders,
    and read or write files through the local bridge.
-   **n8n integration:** Keep the assistant's reasoning and automation
    workflows in n8n, while the Python application handles desktop and
    audio interaction.
-   **Persistent memory through PostgreSQL:** The n8n setup can store
    and retrieve long-term memories in PostgreSQL. Conversation history
    can also use n8n's Postgres Chat Memory node.

The exact actions available depend on the n8n workflows you configure
and the applications installed on your computer.

## Highlights

-   **Modular design:** The Python client, local bridge, and n8n
    workflows have separate responsibilities.
-   **Local desktop control:** Griffin can interact with selected
    applications and files on your Windows machine through a local HTTP
    bridge.
-   **Custom workspace:** File operations are scoped to the `workspace`
    folder inside the Griffin installation.
-   **Automation-friendly:** n8n makes it possible to connect Griffin to
    APIs, services, databases, and scheduled workflows.
-   **Extendable:** You can add your own tools and workflows without
    rebuilding the whole assistant.

## Architecture

``` text
Microphone
    |
    v
Python desktop app
    |
    +------> n8n webhook/workflows ------> AI model
    |                    |
    |                    +---------------> PostgreSQL memory
    |
    +------> Local Windows bridge -------> Applications / workspace files
```

The local bridge listens on `127.0.0.1:8765`. It is intended to be
accessed by the Griffin application on the same computer.

## Requirements

-   Windows 10 or Windows 11
-   Python installed and available from PowerShell
-   Git
-   n8n, running locally or on a server you control
-   A configured n8n voice workflow and an AI model/provider supported
    by that workflow
-   A working microphone and speaker
-   PostgreSQL 18 if you want to reproduce the PostgreSQL memory setup
    described below

The Python dependencies are listed in `requirements.txt`. Audio-library
compatibility depends on your Python version and Windows environment. If
installation fails, try a Python version for which NumPy, SoundDevice,
and SoundFile provide compatible packages.

## Setup

### 1. Get the project

``` powershell
git clone https://github.com/YOUR-GITHUB-USERNAME/Griffin-Public.git
cd Griffin-Public
```

Replace `YOUR-GITHUB-USERNAME` with the GitHub account that hosts your
fork or copy of this repository.

You can also download the repository as a ZIP and extract it.

### 2. Create a virtual environment

``` powershell
python -m venv venv
```

### 3. Install dependencies

``` powershell
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4. Configure the n8n webhook

The Python application reads the voice workflow URL from the
`GRIFFIN_WEBHOOK_URL` environment variable. It is not stored in the
source code.

In PowerShell, set it for your Windows user:

``` powershell
setx GRIFFIN_WEBHOOK_URL "https://YOUR-N8N-HOST/webhook/YOUR-WEBHOOK-PATH"
```

Replace the example URL with the production webhook URL from your own
n8n workflow. Close and reopen PowerShell or GitHub Desktop after using
`setx`, so newly launched processes receive the variable.

Do not commit your real webhook URL, API keys, passwords, or other
credentials.

### 5. Configure your n8n workflow

Create or import your own n8n workflow that accepts the audio request
from Griffin and returns the response in the format expected by the
Python client. The workflow should handle speech transcription, the AI
response, and text-to-speech if you want spoken replies.

**The n8n workflow export is not included in this repository**, so you
must configure the workflow and its credentials separately.

## PostgreSQL and long-term memory setup

Griffin's n8n memory setup uses PostgreSQL. This is separate from the
Python application's local workspace.

### 1. Install and start PostgreSQL

Install PostgreSQL 18 for Windows. Confirm that the Windows service is
running:

``` powershell
Get-Service postgresql-x64-18
```

The service should show as `Running`. Start it from Windows Services if
it is stopped.

### 2. Create the database

Using pgAdmin or `psql`, create a database named:

``` sql
CREATE DATABASE griffin_memory;
```

The established local n8n connection uses:

  Setting    Value
  ---------- ---------------------------------------------------------
  Host       `localhost`
  Port       `5432`
  Database   `griffin_memory`
  Username   `postgres`
  Password   The password chosen during your PostgreSQL installation
  SSL        Disabled for the local setup

Use your own database password. Never put it in this README or commit it
to GitHub.

### 3. Create the long-term memory table

Connect to the `griffin_memory` database and run:

``` sql
CREATE TABLE IF NOT EXISTS griffin_memories (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    memory TEXT NOT NULL,
    category VARCHAR(100),
    source VARCHAR(50) DEFAULT 'chat',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    memory_key TEXT
);
```

The `memory` column stores the memory text. `memory_key` can identify a
specific fact, while `category` can organize memories. Categories used
in the Griffin setup include:

-   `personal`
-   `preference`
-   `project`
-   `technical`

The `source` column can identify where a memory came from, and
`created_at` records when it was saved.

### 4. Connect n8n to PostgreSQL

In n8n:

1.  Create a **Postgres** credential.
2.  Enter the host, database, user, port, and password from the table
    above.
3.  Keep SSL disabled for this local configuration.
4.  Test the credential and save it.

Use the credential in your memory-save and memory-recall database nodes.
A recall workflow can search the `memory`, `memory_key`, and `category`
fields and return the most relevant matching records.

### 5. Optional: conversation history

The Griffin n8n setup also used the **Postgres Chat Memory** node with:

-   Table: `griffin_chat_history`
-   Session key: `griffin-main`
-   Context window: `10`

This is conversation history, separate from the custom
`griffin_memories` table. Configure the node with your PostgreSQL
credential. Depending on your n8n version and node configuration, n8n
may manage the chat-history table schema for you.

> PostgreSQL memory is only available when your n8n workflows are
> configured to save and retrieve it. Installing PostgreSQL alone does
> not automatically give the Python desktop app memory.

## Run Griffin

After creating the virtual environment, installing the dependencies, and
configuring your n8n workflow and webhook:

``` powershell
.\launch_griffin.ps1
```

The launcher starts the local bridge and then the desktop application.
It expects the virtual environment to exist at `venv` inside the project
folder.

If PowerShell blocks the script because of its execution policy, you can
start the components manually:

``` powershell
.\venv\Scripts\python.exe griffin_bridge.py
```

Open a second PowerShell window in the project folder and run:

``` powershell
.\venv\Scripts\python.exe griffin_app.py
```

Keep the bridge running while using desktop-control features.

## Current limitations

Griffin is a work in progress. Some things to be aware of:

-   **Windows-focused:** The bridge and launcher are designed for
    Windows and are not currently a cross-platform desktop-control
    solution.
-   **n8n is required for the assistant workflow:** The Python
    application relies on your configured webhook and workflows. This
    repository does not provide a ready-to-import complete n8n setup.
-   **External services may cost money:** AI models, transcription,
    text-to-speech, and other API services may have usage limits or
    charges depending on your providers.
-   **Microphone and audio setup varies:** Input/output device selection
    and audio-library compatibility can differ between computers.
-   **Not a polished installer:** Setup is manual, and you may need to
    troubleshoot Python packages, n8n credentials, audio devices, or
    webhook configuration.
-   **Local bridge has no authentication yet:** It binds to localhost,
    but another process running on your computer may still be able to
    send it requests. Do not expose port `8765` to your network or the
    public internet.
-   **Workspace scope:** File operations are intended for the project's
    `workspace` folder, not unrestricted access to the entire computer.
-   **Memory depends on workflow design:** PostgreSQL stores data, but
    the quality of recall depends on how your n8n workflows save,
    search, and use those memories.

This project is experimental. Do not use it as a security boundary or
give it access to sensitive files or accounts.

## Ideas you can add

Griffin is designed to be extended. Some possible additions:

-   **Wake-word detection:** Add a custom wake word such as "Hey
    Griffin".
-   **Continuous conversation:** Add a listening loop with voice
    activity detection and interruption handling.
-   **More desktop tools:** Add controlled actions for additional
    applications, window management, or other local tasks.
-   **Scheduled automations:** Use n8n schedules for reminders, daily
    summaries, and recurring tasks.
-   **More integrations:** Connect calendars, email, task managers,
    smart-home systems, or other APIs through n8n.
-   **Knowledge retrieval:** Add document search or a
    retrieval-augmented generation (RAG) workflow.
-   **Additional voices and languages:** Configure different
    speech-to-text and text-to-speech providers.
-   **A safer permission system:** Add authentication, per-action
    approval, and a clear allowlist for bridge operations.
-   **A setup wizard:** Make first-time configuration easier by guiding
    users through Python, n8n, PostgreSQL, and audio settings.

These are ideas for contributors and users to implement; they are not
all included in the current version.

## Security notes

-   Keep API keys, passwords, webhook URLs, and `.env` files out of Git.
-   Keep the bridge bound to `127.0.0.1`; do not port-forward it or
    expose it through a tunnel.
-   Do not store sensitive personal documents in the Griffin workspace.
-   Review any new computer-control actions before enabling them.
-   Remember that n8n workflows and connected services may process or
    store the information you send them.

## Project structure

``` text
Griffin-Public/
├── griffin.py
├── griffin_app.py
├── griffin_bridge.py
├── griffin_gui.py
├── launch_griffin.ps1
├── requirements.txt
├── .gitignore
└── workspace/
    └── .gitkeep
```

## Contributing

Ideas, bug reports, and improvements are welcome. If you add a new
feature, please document its requirements and any permissions or
external services it needs.

## Disclaimer

Griffin is an independent personal project. It is not affiliated with
OpenAI, Microsoft, or any other AI provider. You are responsible for
configuring your own services, protecting your credentials, and
reviewing the actions you enable.
