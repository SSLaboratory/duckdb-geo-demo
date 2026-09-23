from fastapi import HTTPException, Request


def require_writable(request: Request) -> None:
    if request.app.state.settings.read_only:
        raise HTTPException(status_code=403, detail="This deployment is read-only")
