# SPD Devcontainer - Multi-Runtime Development Environment
# Base: Node 20 LTS + Python 3.11 + PostgreSQL Client + Development Tools

FROM node:20-slim

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install Python 3.11, PostgreSQL client, and essential development tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Python runtime and tools
    python3.11 \
    python3.11-venv \
    python3-pip \
    python3.11-dev \
    # PostgreSQL client tools
    postgresql-client \
    # Build essentials for native dependencies
    build-essential \
    # Version control
    git \
    git-lfs \
    # Network tools
    curl \
    wget \
    ca-certificates \
    # Process tools
    procps \
    # Text editing (basic vim)
    vim \
    # Compression tools
    zip \
    unzip \
    # Make for running Makefile commands
    make \
    # Docker CLI for docker-compose access
    docker.io \
    # GitHub CLI for CI interaction
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    # Cleanup
    && rm -rf /var/lib/apt/lists/*

# Create python3 symlink to python3.11
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

# Remove externally-managed environment marker (safe for containers)
# This allows pip to install packages system-wide in the devcontainer
RUN rm -f /usr/lib/python3.11/EXTERNALLY-MANAGED

# Upgrade pip
RUN python3 -m pip install --upgrade pip setuptools wheel

# Install mise for version management (root)
RUN curl https://mise.run | sh

# Add mise to PATH for all users
ENV PATH="/root/.local/bin:${PATH}"

# Install sudo first (needed for devcontainer features)
RUN apt-get update \
    && apt-get install -y sudo \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for development
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000

# Check if group/user already exists (node:20-slim has node user with UID 1000)
# If so, modify existing user; otherwise create new one
RUN if getent passwd $USER_UID >/dev/null 2>&1; then \
        # User with UID 1000 exists (node user), rename it to vscode \
        existing_user=$(getent passwd $USER_UID | cut -d: -f1); \
        usermod -l $USERNAME $existing_user; \
        groupmod -n $USERNAME $existing_user; \
        usermod -d /home/$USERNAME -m $USERNAME; \
    else \
        # Create new user \
        groupadd --gid $USER_GID $USERNAME; \
        useradd --uid $USER_UID --gid $USER_GID -m $USERNAME; \
    fi \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# Install mise for non-root user
USER $USERNAME
RUN curl https://mise.run | sh
ENV PATH="/home/${USERNAME}/.local/bin:${PATH}"

# Add mise activation to bashrc for automatic PATH setup
RUN echo 'eval "$(mise activate bash)"' >> ~/.bashrc

# Set working directory
WORKDIR /workspace

# Switch back to root for container initialization
USER root

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NODE_ENV=development

# Default command
CMD ["/bin/bash"]
