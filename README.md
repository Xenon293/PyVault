# Password Manager

A local desktop password manager built with Python and Tkinter. Store usernames and passwords in an encrypted vault on your machine, unlocked with a single master password.

## Features

- **Master password unlock** — one password protects the entire vault
- **Encrypted credential storage** — add, view, and manage saved credentials securely
- **Vault reset** — wipe the vault and start fresh when needed

## Tech Stack

- **Python** — application runtime
- **Tkinter** — desktop GUI
- **cryptography** — Fernet (authenticated encryption) and PBKDF2HMAC (key derivation)

## Setup

### Prerequisites

- Python 3.10 or later

### Installation

```bash
git clone <your-repo-url>
cd "Password Manager"

python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Run

```bash
python "Password Manager.py"
```

## Usage

**First run:** The app prompts you to create a master password. This password derives the encryption key for your vault — choose something strong and memorable.

**Subsequent runs:** Enter your master password to unlock the vault. You can then add, view, and manage stored credentials.

**Vault reset:** Use the in-app reset option to delete all stored credentials and set a new master password. This action is permanent.

## Project Structure

```
Password Manager/
├── Password Manager.py    # Application entry point
├── password_manager/      # MVC application package
│   ├── app.py
│   ├── models/
│   └── views/
└── requirements.txt
```

## Security Notes

- **Key derivation:** The master password is stretched with PBKDF2-HMAC-SHA256 using **600,000 iterations** before it is used to encrypt or decrypt data.
- **Encryption:** Credentials are protected with **Fernet**, which provides authenticated encryption — tampering with vault data is detected on unlock.
- **Local storage only:** Vault files (`vault.txt`, `salt.bin`, `secret.key`, and related files) are stored on your machine and listed in `.gitignore` so they are never committed to version control.
- **Your responsibility:** There is no cloud backup or account recovery. If you forget the master password, stored credentials cannot be recovered.

## License

Private project — not licensed for public distribution unless otherwise stated.
