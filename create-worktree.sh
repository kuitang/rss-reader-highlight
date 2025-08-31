#!/bin/bash

set -e

BRANCH_NAME="$1"
COPY_DB_FLAG="$2"

if [ -z "$BRANCH_NAME" ]; then
    echo "Usage: $0 <branch-name> [--copy-db]"
    echo "Example: $0 feature-auth"
    echo "         $0 bugfix-feeds --copy-db"
    exit 1
fi

# Validate branch name
if [[ ! "$BRANCH_NAME" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "Error: Branch name can only contain letters, numbers, hyphens, and underscores"
    exit 1
fi

WORKTREE_DIR="../rss-reader-$BRANCH_NAME"
BASE_PORT=5001

# Function to find next available port
find_next_port() {
    local port=$BASE_PORT
    
    # Skip base port if we're in main directory (it's reserved for main worktree)
    if [ "$(basename $(pwd))" = "rss-reader-highlight" ]; then
        ((port++))
    fi
    
    while [ $port -le 5050 ]; do
        # Check if port is in use by network
        if ! netstat -tuln 2>/dev/null | grep -q ":$port "; then
            # Check if port is already assigned to another worktree
            local port_in_use=false
            for env_file in ../rss-reader-*/.env; do
                if [ -f "$env_file" ] && grep -q "PORT=$port" "$env_file"; then
                    port_in_use=true
                    break
                fi
            done
            
            if [ "$port_in_use" = false ]; then
                echo $port
                return
            fi
        fi
        ((port++))
    done
    echo "Error: No available ports found between $BASE_PORT and 5050" >&2
    exit 1
}

# Check if worktree already exists
if [ -d "$WORKTREE_DIR" ]; then
    echo "Error: Worktree directory $WORKTREE_DIR already exists"
    exit 1
fi

echo "Creating worktree for branch: $BRANCH_NAME"

# Create git worktree
if git show-ref --verify --quiet "refs/heads/$BRANCH_NAME"; then
    echo "Checking out existing branch: $BRANCH_NAME"
    git worktree add "$WORKTREE_DIR" "$BRANCH_NAME"
else
    echo "Creating new branch: $BRANCH_NAME"
    git worktree add -b "$BRANCH_NAME" "$WORKTREE_DIR"
fi

# Find next available port
WORKTREE_PORT=$(find_next_port)
echo "Assigned port: $WORKTREE_PORT"

# Create data directory in worktree
mkdir -p "$WORKTREE_DIR/data"

# Handle database setup
if [ "$COPY_DB_FLAG" = "--copy-db" ] && [ -f "data/rss.db" ]; then
    echo "Copying existing database..."
    cp "data/rss.db" "$WORKTREE_DIR/data/rss.db"
    # Also copy any WAL files if they exist
    [ -f "data/rss.db-wal" ] && cp "data/rss.db-wal" "$WORKTREE_DIR/data/"
    [ -f "data/rss.db-shm" ] && cp "data/rss.db-shm" "$WORKTREE_DIR/data/"
else
    echo "Creating fresh database (will setup default feeds on first run)..."
fi

# Create .env file
cat > "$WORKTREE_DIR/.env" << EOF
# Environment configuration for worktree: $BRANCH_NAME
PORT=$WORKTREE_PORT
DATABASE_PATH=data/rss.db
EOF

# Create run.sh launcher script
cat > "$WORKTREE_DIR/run.sh" << 'EOF'
#!/bin/bash

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "../rss-reader-highlight/venv" ]; then
    source ../rss-reader-highlight/venv/bin/activate
fi

echo "Starting RSS Reader on port $PORT"
echo "Database: $DATABASE_PATH"
echo "Access at: http://localhost:$PORT"
echo ""

python app.py
EOF

# Make launcher executable
chmod +x "$WORKTREE_DIR/run.sh"

# Create info file for easy reference
cat > "$WORKTREE_DIR/WORKTREE_INFO.md" << EOF
# Worktree: $BRANCH_NAME

- **Port**: $WORKTREE_PORT
- **Database**: data/rss.db ($([ "$COPY_DB_FLAG" = "--copy-db" ] && echo "copied from main" || echo "fresh"))
- **URL**: http://localhost:$WORKTREE_PORT

## Commands
- Start server: \`./run.sh\`
- Run tests: \`python -m pytest\`
- Access main worktree: \`cd ../rss-reader-highlight\`

## Cleanup
To remove this worktree:
\`\`\`bash
cd ../rss-reader-highlight
git worktree remove ../rss-reader-$BRANCH_NAME
\`\`\`
EOF

echo ""
echo "✅ Worktree created successfully!"
echo "📂 Location: $WORKTREE_DIR"
echo "🌐 Port: $WORKTREE_PORT"
echo "💾 Database: $([ "$COPY_DB_FLAG" = "--copy-db" ] && echo "Copied from main" || echo "Fresh (default feeds will be added on first run)")"
echo ""
echo "🚀 To start:"
echo "   cd $WORKTREE_DIR"
echo "   ./run.sh"
echo ""
echo "🌍 Then visit: http://localhost:$WORKTREE_PORT"