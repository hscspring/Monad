# Tool: python_exec

MONAD 的核心能力——执行 Python 代码。

## Description

Execute arbitrary Python code. This is MONAD's most powerful capability.
Through python_exec, MONAD can learn to do anything.

## Capabilities

- Call APIs (requests, urllib)
- Read/write files
- Process data
- Check network connectivity
- Install packages (subprocess)
- Mathematical calculations
- Data analysis

## Input

- code: Python code string to execute

## Output

stdout output from the executed code, or error traceback.

## Usage Notes

- Always include `print()` statements to see output
- Import libraries at the top of each code block
- Handle exceptions gracefully
