"""gunicorn settings, loaded automatically from the working directory (ADR 0008)."""

bind = "0.0.0.0:8000"
# Sync workers: the views are synchronous.
workers = 2
# The container's filesystem is read-only; /dev/shm is a tmpfs.
worker_tmp_dir = "/dev/shm"  # noqa: S108 - heartbeat files only, in a private container
# No gunicornc control socket: unused, and it would need a writable path.
control_socket_disable = True
accesslog = "-"
