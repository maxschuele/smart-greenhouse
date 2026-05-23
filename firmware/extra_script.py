import os

Import("env")  # noqa: F821  (injected by PlatformIO)


# Load build-time defines from firmware/.env (shared) and firmware/<project>/.env
# (per-node overrides). Values are injected as -DKEY=\"value\" build flags.
def _load_env_file(path):
    if not os.path.isfile(path):
        return
    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            env.Append(BUILD_FLAGS=[f'-D{key}=\\"{val}\\"'])  # noqa: F821


_project_dir = env["PROJECT_DIR"]  # noqa: F821
_firmware_dir = os.path.dirname(_project_dir)
_load_env_file(os.path.join(_firmware_dir, ".env"))
_load_env_file(os.path.join(_project_dir, ".env"))


env.Replace(COMPILATIONDB_INCLUDE_TOOLCHAIN=True)
