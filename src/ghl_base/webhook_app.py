import os
import importlib
import logging
import pkgutil
import hashlib
import hmac
import time
import uuid
import sys
from typing import Iterable, List, Tuple, Callable, Any

from aiohttp import web

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


def _iter_modules_from_env() -> List[object]:
    # Ensure local project root is importable (console_scripts don't include CWD)
    try:
        cwd = os.getcwd()
        if cwd and cwd not in sys.path:
            sys.path.insert(0, cwd)
    except Exception:
        pass

    raw = os.getenv("WEBHOOK_HANDLERS", "handlers.webhooks").strip()
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    loaded: List[object] = []

    for part in parts:
        try:
            if part.endswith(".*"):
                pkg_name = part[:-2]
                pkg = importlib.import_module(pkg_name)
                if hasattr(pkg, "__path__"):
                    for _, name, _ in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
                        try:
                            loaded.append(importlib.import_module(name))
                        except Exception as e:
                            logging.exception("Falha importando submódulo %s: %s", name, e)
                else:
                    loaded.append(pkg)
            else:
                loaded.append(importlib.import_module(part))
        except Exception as e:
            logging.exception("Falha importando módulo %s: %s", part, e)

    if not loaded:
        # Fallbacks within this repo structure
        for fallback in ("handlers.webhooks", "examples.handlers.*"):
            try:
                if fallback.endswith(".*"):
                    pkg_name = fallback[:-2]
                    pkg = importlib.import_module(pkg_name)
                    if hasattr(pkg, "__path__"):
                        for _, name, _ in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
                            try:
                                loaded.append(importlib.import_module(name))
                            except Exception as e:
                                logging.exception("Falha importando submódulo %s: %s", name, e)
                    else:
                        loaded.append(pkg)
                else:
                    loaded.append(importlib.import_module(fallback))
            except Exception:
                continue
            if loaded:
                break
    return loaded


RouteSpec = Tuple[str, str, Callable[..., Any]]


def _collect_routes_and_hooks(modules: Iterable[object]):
    route_specs: List[RouteSpec] = []
    route_tables: List[Any] = []
    middlewares: List[Callable] = []
    startups: List[Callable[[web.Application], Any]] = []
    cleanups: List[Callable[[web.Application], Any]] = []

    for m in modules:
        routes = getattr(m, "ROUTES", None)
        if routes is not None:
            if hasattr(routes, "__iter__") and not hasattr(routes, "register"):
                for item in routes:
                    try:
                        method, path, handler = item
                        if not isinstance(method, str) or not isinstance(path, str) or not callable(handler):
                            raise ValueError("ROUTES inválido: esperado (method:str, path:str, handler:callable)")
                        route_specs.append((method.upper(), path, handler))
                    except Exception as e:
                        logging.exception("Ignorando rota inválida em %s: %s", getattr(m, "__name__", m), e)
            else:
                route_tables.append(routes)

        mws = getattr(m, "MIDDLEWARES", None)
        if mws:
            for mw in mws:
                if callable(mw):
                    middlewares.append(mw)

        on_startup = getattr(m, "on_startup", None)
        if callable(on_startup):
            startups.append(on_startup)
        on_cleanup = getattr(m, "on_cleanup", None)
        if callable(on_cleanup):
            cleanups.append(on_cleanup)

    return route_specs, route_tables, middlewares, startups, cleanups


@web.middleware
async def _request_id_logging_middleware(request: web.Request, handler):
    start = time.time()
    req_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
    request["request_id"] = req_id

    try:
        logging.info("--> %s %s rid=%s", request.method, request.path_qs, req_id)
        resp: web.StreamResponse = await handler(request)
        return resp
    finally:
        duration = (time.time() - start) * 1000
        logging.info("<-- %s %s rid=%s %.2fms", request.method, request.path_qs, req_id, duration)


def _constant_time_compare(a: str, b: str) -> bool:
    try:
        return hmac.compare_digest(a, b)
    except Exception:
        if len(a) != len(b):
            return False
        result = 0
        for x, y in zip(a.encode(), b.encode()):
            result |= x ^ y
        return result == 0


@web.middleware
async def _signature_middleware(request: web.Request, handler):
    secret = os.getenv("WEBHOOK_SECRET")
    if not secret:
        return await handler(request)

    header_name = os.getenv("WEBHOOK_SIGNATURE_HEADER", "X-Signature")
    algo = os.getenv("WEBHOOK_SIGNATURE_ALGO", "sha256").lower()
    provided = request.headers.get(header_name)
    if not provided:
        return web.Response(status=401, text="missing signature")

    body = await request.read()
    try:
        setattr(request, "_read_bytes", body)
    except Exception:
        pass

    if algo not in ("sha256", "sha1"):
        return web.Response(status=400, text="unsupported signature algo")

    digestmod = hashlib.sha256 if algo == "sha256" else hashlib.sha1
    mac = hmac.new(secret.encode(), body, digestmod=digestmod).hexdigest()
    if provided.startswith(f"{algo}="):
        provided = provided.split("=", 1)[1]

    if not _constant_time_compare(mac, provided):
        return web.Response(status=401, text="invalid signature")

    request["raw_body"] = body
    return await handler(request)


class _TTLMemory:
    def __init__(self, ttl_seconds: int = 600):
        self.ttl = ttl_seconds
        self._store: dict[str, float] = {}

    def seen(self, key: str) -> bool:
        now = time.time()
        if len(self._store) > 2048:
            self._store = {k: exp for k, exp in self._store.items() if exp > now}
        exp = self._store.get(key)
        if exp and exp > now:
            return True
        return False

    def put(self, key: str):
        self._store[key] = time.time() + self.ttl


_idemp_cache = _TTLMemory(ttl_seconds=int(os.getenv("IDEMPOTENCY_TTL_SECONDS", "600")))


@web.middleware
async def _idempotency_middleware(request: web.Request, handler):
    if os.getenv("IDEMPOTENCY_ENABLED", "true").lower() not in ("1", "true", "yes", "on"):
        return await handler(request)

    headers_raw = os.getenv("IDEMPOTENCY_HEADERS", "Idempotency-Key,X-Event-Id")
    header_names = [h.strip() for h in headers_raw.split(",") if h.strip()]
    key = None
    for name in header_names:
        key = request.headers.get(name)
        if key:
            break
    if not key:
        return await handler(request)

    if _idemp_cache.seen(key):
        resp = web.json_response({"status": "duplicate"})
        resp.headers["X-Idempotent-Replayed"] = "true"
        return resp

    _idemp_cache.put(key)
    return await handler(request)


def build_app():
    middlewares: List[Callable] = [
        _request_id_logging_middleware,
        _signature_middleware,
        _idempotency_middleware,
    ]

    modules = _iter_modules_from_env()
    route_specs, route_tables, mod_mws, startups, cleanups = _collect_routes_and_hooks(modules)
    middlewares.extend(mod_mws)

    app = web.Application(middlewares=middlewares)

    async def _health(_: web.Request):
        return web.Response(text="ok")

    app.router.add_get("/healthz", _health)

    for method, path, handler in route_specs:
        app.router.add_route(method, path, handler)
    for table in route_tables:
        try:
            app.add_routes(table)
        except Exception as e:
            logging.exception("Falha registrando RouteTableDef: %s", e)

    for cb in startups:
        app.on_startup.append(cb)
    for cb in cleanups:
        app.on_cleanup.append(cb)

    app["webhook_modules"] = [getattr(m, "__name__", str(m)) for m in modules]
    return app


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app = build_app()
    port = int(os.getenv("PORT", "8081"))
    logging.info("Subindo webhook server na porta %s", port)
    web.run_app(app, port=port)


if __name__ == "__main__":
    main()
