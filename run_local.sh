#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Set working directory to the directory where this script is located
cd "$(dirname "$0")"

# Colors for pretty output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0;m' # No Color

echo -e "${GREEN}=== Starting Django Local Runner ===${NC}"

# 1. Prerequisite Check: Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed or not in PATH.${NC}" >&2
    exit 1
fi

# 2. Virtual Environment Setup
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Creating virtual environment (.venv)...${NC}"
    python3 -m venv .venv
else
    echo -e "${GREEN}Virtual environment (.venv) already exists.${NC}"
fi

echo -e "${YELLOW}Activating virtual environment...${NC}"
source .venv/bin/activate

# 3. Dependency Installation
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip

if [ -f "requirements.txt" ]; then
    echo -e "${YELLOW}Installing/updating python dependencies from requirements.txt...${NC}"
    pip install -r requirements.txt
else
    echo -e "${RED}Warning: requirements.txt not found!${NC}"
fi

# 4. Environment Variables Configuration
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}.env file not found. Copying from .env.example...${NC}"
    cp .env.example .env
    
    # Generate a secure random Django SECRET_KEY and update it in .env
    SECURE_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
    
    # Use python for the replacement to be perfectly platform-independent
    python3 -c "
with open('.env', 'r') as f:
    content = f.read()
content = content.replace('SECRET_KEY=change-me-in-production', 'SECRET_KEY=${SECURE_KEY}')
with open('.env', 'w') as f:
    f.write(content)
"
    echo -e "${GREEN}Generated new secure SECRET_KEY in .env.${NC}"
else
    echo -e "${GREEN}.env file already exists.${NC}"
fi

# 5. Database Migration
echo -e "${YELLOW}Running database migrations...${NC}"
python manage.py migrate --noinput

# 6. Dependency Health Checks (Redis)
echo -e "${YELLOW}Checking Redis status...${NC}"
# Use python socket to check port 6379 connectivity
REDIS_RUNNING=$(python3 -c "
import socket
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    s.connect(('127.0.0.1', 6379))
    s.close()
    print('true')
except Exception:
    print('false')
")

if [ "$REDIS_RUNNING" = "true" ]; then
    echo -e "${GREEN}Redis is running on localhost:6379.${NC}"
else
    echo -e "${YELLOW}Warning: Redis is not running on localhost:6379.${NC}"
    echo -e "${YELLOW}WebSockets/Channels will not function properly without Redis.${NC}"
    echo -e "${YELLOW}You can start Redis locally using your package manager (e.g. sudo apt install redis-server)${NC}"
fi

# 7. Start Django/Daphne server
echo -e "${GREEN}Starting Django development server at http://127.0.0.1:8000 ...${NC}"
echo -e "${GREEN}Press Ctrl+C to stop.${NC}"
python manage.py runserver 127.0.0.1:8000
