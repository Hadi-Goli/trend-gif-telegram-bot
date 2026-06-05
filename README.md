<div align="center">
  <h1>🎬 Trend GIF Telegram Bot</h1>
  <p><strong>A fully automated, asynchronous Telegram bot with FFmpeg integration, community submissions, and CI/CD pipelines.</strong></p>
  
  [![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://python.org)
  [![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?logo=docker&logoColor=white)](https://docker.com)
  [![FFmpeg](https://img.shields.io/badge/FFmpeg-Media%20Engine-5G6438?logo=ffmpeg&logoColor=white)](https://ffmpeg.org)
  [![Telegram API](https://img.shields.io/badge/PTB-v20+-2CA5E0?logo=telegram&logoColor=white)](https://python-telegram-bot.org/)
  [![GitHub Actions](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF?logo=github-actions&logoColor=white)](https://github.com/features/actions)

  <br>
  <i>Read this in <a href="README_FA.md">Persian (فارسی)</a></i>
</div>

---

## 📌 Overview
An enterprise-grade, asynchronous Telegram Bot designed to streamline media publishing for Telegram channels. It processes video and animation (GIF) files, applies customized text watermarks dynamically using **FFmpeg**, and publishes them to a target channel—all while running securely in an isolated Docker container via **HTTPS Webhooks**.

The bot also features a **Community Submission System** that allows public users to submit GIFs for channel publication, with a full admin moderation workflow and tiered anti-spam protection.

This project serves as a showcase of modern Python backend development, DevOps practices (Docker + CI/CD), and robust API integration.

## 🚀 Key Features

*   **Asynchronous Webhook Architecture**: Transitioned from polling to a secure, high-performance HTTPS webhook model for production readiness.
*   **Media Processing Engine**: Seamless integration with FFmpeg via `asyncio.subprocess` to manipulate video streams, apply styling (shadows, fonts), and strip audio tracks dynamically.
*   **Community GIF Submissions**: Public users can submit GIFs with hashtags and credit names. Submissions go through a moderated review process before publication.
*   **Admin Moderation Workflow**: Admins review submissions in a dedicated Telegram group with inline buttons—claim, edit hashtags, approve, or reject—all without leaving the group chat.
*   **Tiered Anti-Spam Protection**: Progressive rate limiting (10 free → 3/10min → 1/30min → daily lock) prevents abuse while allowing genuine contributions.
*   **DevOps & CI/CD Pipeline**: Fully automated deployments to a remote server using GitHub Actions, SCP, and SSH. 
*   **Dockerized Environment**: The bot and all its complex system dependencies (like FFmpeg) are encapsulated in a lightweight container, ensuring complete environment parity.
*   **Persistent Logging**: Integrates Python's `RotatingFileHandler` mapped securely to Docker volumes, enabling historical debugging without infinite disk consumption.
*   **State Management without FSM**: Clever use of Telegram's `ForceReply` and `context.user_data` mapping to track active video processing sessions seamlessly.
*   **Strict Access Control**: Granular permission layers ensuring only the `OWNER_ID` or registered `admins` in the local SQLite database can trigger admin commands.

## 🛠️ Tech Stack & Architecture

- **Language:** Python 3.13
- **Framework:** `python-telegram-bot` (v20+)
- **Database:** SQLite3
- **Media Processing:** FFmpeg
- **Infrastructure:** Docker, Docker Compose
- **CI/CD:** GitHub Actions (Automated SSH & SCP)

### System Workflow
```mermaid
graph TD
    subgraph Admin Flow
        A[Admin User] -->|Sends Animation/Video| B[Telegram Bot Webhook]
        B -->|Checks DB Permissions| C{Is Admin?}
        C -->|Yes| E[Prompt for Hashtag]
        E -->|Select Tags + Confirm| F[FFmpeg Watermark]
        F --> G[Publish to Channel]
    end

    subgraph Community Submission Flow
        U[Public User] -->|/start| B
        B -->|Show Submit Button| U
        U -->|Sends GIF + Tags + Name| B
        B -->|Rate Limit Check| RL{Allowed?}
        RL -->|No| WAIT[Show Wait Message]
        RL -->|Yes| RG[Send to Review Group]
        RG -->|Admin Claims| CLAIM[🔒 Locked to Admin]
        CLAIM -->|Edit Tags / Approve / Reject| REVIEW{Decision}
        REVIEW -->|✅ Approve| F2[FFmpeg Watermark]
        F2 --> G2[Publish to Channel + Notify User]
        REVIEW -->|❌ Reject| NOTIFY[Notify User: Rejected]
    end
```

## 📁 Repository Structure

*   `bot.py`: The main asynchronous webhook application. Handles request routing, state management, and API calls.
*   `community.py`: Community GIF submission flow — user-facing interaction from submit button through hashtag selection and name confirmation.
*   `review.py`: Admin review flow — handles claim/edit/approve/reject entirely within the review group using inline keyboards.
*   `video.py`: The FFmpeg media processing pipeline, utilizing `asyncio.create_subprocess_exec`.
*   `db.py`: The Data Access Object (DAO) managing SQLite connections, admin whitelists, submissions, rate limits, and logging.
*   `Dockerfile` & `docker-compose.yml`: Container orchestration definitions.
*   `.github/workflows/deploy.yml`: The CI/CD pipeline for automated deployments.

## ⚙️ Configuration & Environment Variables

The bot utilizes environment variables to ensure secrets are never leaked into version control. You must provide these variables either in a `.env` file or directly in the CI/CD pipeline (via GitHub Secrets):

| Variable | Description | Example |
| :--- | :--- | :--- |
| `BOT_TOKEN` | Token provided by @BotFather | `123456789:ABCDEF...` |
| `IP_ADDRESS` | Public IP of the host server | `45.91.248.25` |
| `PORT` | Webhook listening port | `8443` |
| `KEYBOARD_MODE` | UI Type for hashtags (`INLINE` or `REPLY`) | `INLINE` |
| `REVIEW_GROUP_ID` | Numeric ID of the admin review Telegram group | `-1001234567890` |

*Note: For the webhook to function securely, `public.pem` and `private.key` SSL certificates must exist in the root directory.*

## 🚀 Deployment (CI/CD)

This project features a fully automated CI/CD pipeline. Pushing to the `main` branch triggers a GitHub Action that:
1. Connects to the host server via SSH.
2. Synchronizes the latest codebase securely using SCP.
3. Injects the production secrets into a `.env` file dynamically.
4. Rebuilds and restarts the Docker containers seamlessly without downtime.

### Manual Local Setup (Development)

1. Clone the repository and navigate inside.
2. Create a `.env` file based on `.env.example`.
3. Run with Docker Compose:
```bash
docker compose up -d --build
```

## 🛡️ Administrative Commands (Owner Only)
*   `/start`: Bot health check.
*   `/add_admin <user_id>`: Whitelists a new administrator.
*   `/remove_admin <user_id>`: Revokes administrator access.
*   `/list_admins`: Displays a list of all current administrators.
*   `/add_tag <hashtag>`: Registers a new category tag.
*   `/remove_tag <hashtag>`: Deletes an existing tag.
*   `/list_tags`: Displays all available hashtags (available to both Owner and Admins).
*   `/report`: Generates monthly activity statistics per administrator.
*   `/pending`: Shows count of GIFs awaiting admin review.

## 📤 Community Submission (Public Users)
*   `/start`: Welcome message with "📤 Submit GIF" button.
*   `/help`: Usage guide for submitting GIFs.
*   `/cancel`: Cancel an active submission flow.
