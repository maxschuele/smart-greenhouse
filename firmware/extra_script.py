import os

Import("env")  # noqa: F821  (injected by PlatformIO)

# Write compile_commands.json to the project root instead of .pio/build/<env>/
# so clangd (which searches upward from the edited file) picks it up.
env["COMPILATIONDB_PATH"] = os.path.join("$PROJECT_DIR", "compile_commands.json")  # noqa: F821

# Note: COMPILATIONDB_INCLUDE_TOOLCHAIN=True is documented to embed toolchain
# include paths into each compile_commands.json entry, but in PlatformIO 6.1.19
# the appended CPPPATH does not propagate to the emitted command lines. Toolchain
# paths are therefore declared in ../.clangd via -isystem. Revisit if PIO fixes it.
