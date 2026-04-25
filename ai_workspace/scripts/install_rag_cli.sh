#!/bin/bash
# RAG CLI Installer

# Get RAG_ROOT dynamically
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RAG_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

install_rag_cli() {
    local shellrc="$HOME/.zshrc"
    
    if grep -q "RAG CLI" "$shellrc" 2>/dev/null; then
        echo "RAG CLI already installed."
        return
    fi
    
    cat >> "$shellrc" << EOF

# RAG CLI
export RAG_ROOT="$RAG_ROOT"

rag() {
    cd "$RAG_ROOT" && python scripts/rag_cli.py "${1:-status}"
}

alias rag-set="rag set-embedding"
EOF
    
    echo "Installed to $shellrc"
    echo "Run: rag status"
}

uninstall_rag_cli() {
    sed -i '/# RAG CLI/,/alias rag-on/d' "$HOME/.zshrc" 2>/dev/null
    echo "Removed"
}

case "${1:-install}" in
    install) install_rag_cli ;;
    uninstall) uninstall_rag_cli ;;
    *) echo "Usage: $0 [install|uninstall]" ;;
esac