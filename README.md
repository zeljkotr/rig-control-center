# RIG Control Center

**Centralized Mining Infrastructure Management Platform**

RIG Control Center is a self-hosted web application designed to manage, monitor, and control Linux-based mining infrastructure from a single dashboard.

## Features

- Centralized management of multiple mining rigs
- Remote Linux server connectivity over SSH
- SSH key-based authentication
- Remote server and connection monitoring
- Mining worker monitoring
- Mining pool management
- Shared Monero wallet configuration
- Unique Worker ID for each rig
- Centralized mining configuration
- Web-based management dashboard
- Persistent local configuration and database

## Architecture

- **Backend:** Python, FastAPI
- **Database:** SQLite, SQLAlchemy
- **Frontend:** HTML5, CSS3, JavaScript
- **Remote connectivity:** Paramiko, SSH
- **Deployment:** Linux

## Installation

Clone the repository:

    git clone https://github.com/zeljkotr/rig-control-center.git
    cd rig-control-center

Create a virtual environment:

    python3 -m venv .venv
    source .venv/bin/activate

Install dependencies according to the project dependency configuration.

## SSH Infrastructure

RIG Control Center connects to remote Linux servers using SSH key-based authentication.

Each managed host requires:
- SSH service enabled
- A valid SSH account
- The shared public key in authorized_keys
- A verified SSH host key

Private SSH keys must remain on the control server.

## Mining Configuration

- One shared Monero wallet address can be used across all rigs.
- Every rig must have its own unique Worker ID.
- Worker IDs identify individual rig activity in the mining pool.

## Security

- Never commit passwords, tokens, or private keys.
- Keep environment files outside version control.
- Verify SSH host fingerprints.
- Restrict remote access to authorized accounts.
- Keep local databases and backups out of Git.

## License

License information will be published separately.
