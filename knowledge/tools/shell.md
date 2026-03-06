# Tool: shell

Execute shell commands on the operating system.

## Description

Run terminal/shell commands and return the output.

## Input

- command: Shell command string
- timeout: Maximum execution time (default: 30s)

## Output

Command stdout/stderr output.

## Usage Notes

- Use for system operations (ls, mkdir, pip install, etc.)
- Set appropriate timeout for long-running commands
- Be careful with destructive commands
