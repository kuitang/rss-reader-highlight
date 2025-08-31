#!/bin/bash

# Worktree management script

case "$1" in
    "list"|"ls")
        echo "📂 Git Worktrees:"
        git worktree list
        echo ""
        echo "🌐 Port Assignments:"
        for env_file in ../rss-reader-*/.env; do
            if [ -f "$env_file" ]; then
                worktree_name=$(basename $(dirname "$env_file"))
                app_port=$(grep "^PORT=" "$env_file" | cut -d'=' -f2)
                playwright_port=$(grep "^PLAYWRIGHT_MCP_PORT=" "$env_file" | cut -d'=' -f2)
                echo "  $worktree_name → App:$app_port, MCP:${playwright_port:-N/A}"
            fi
        done
        ;;
    "create")
        shift
        ./create-worktree.sh "$@"
        ;;
    "remove"|"rm")
        if [ -z "$2" ]; then
            echo "Usage: $0 remove <branch-name>"
            exit 1
        fi
        BRANCH_NAME="$2"
        WORKTREE_DIR="../rss-reader-$BRANCH_NAME"
        
        if [ ! -d "$WORKTREE_DIR" ]; then
            echo "Error: Worktree $WORKTREE_DIR not found"
            exit 1
        fi
        
        echo "Removing worktree: $BRANCH_NAME"
        git worktree remove --force "$WORKTREE_DIR"
        echo "✅ Worktree removed successfully"
        ;;
    "ports")
        echo "🌐 Port Status:"
        for port in {5001..5010}; do
            if netstat -tuln 2>/dev/null | grep -q ":$port "; then
                echo "  $port: 🔴 In use"
            else
                # Check if assigned to worktree
                assigned=""
                for env_file in ../rss-reader-*/.env; do
                    if [ -f "$env_file" ] && grep -q "PORT=$port" "$env_file"; then
                        worktree_name=$(basename $(dirname "$env_file"))
                        assigned=" (assigned to $worktree_name)"
                        break
                    fi
                done
                if [ -n "$assigned" ]; then
                    echo "  $port: 🟡 Assigned$assigned"
                else
                    echo "  $port: 🟢 Available"
                fi
            fi
        done
        ;;
    "help"|"")
        echo "RSS Reader Worktree Manager"
        echo ""
        echo "Usage: $0 <command> [args]"
        echo ""
        echo "Commands:"
        echo "  list, ls          List all worktrees and their ports"
        echo "  create <branch>   Create new worktree"
        echo "  create <branch> --copy-db  Create worktree with copied database"
        echo "  remove <branch>   Remove worktree"
        echo "  ports             Show port usage status"
        echo "  help              Show this help"
        echo ""
        echo "Examples:"
        echo "  $0 create feature-auth"
        echo "  $0 create bugfix --copy-db"
        echo "  $0 list"
        echo "  $0 remove feature-auth"
        ;;
    *)
        echo "Unknown command: $1"
        echo "Run '$0 help' for usage information"
        exit 1
        ;;
esac