"""HTTP exposure — FastAPI routers, thin layer over api/.

Section 8 of the lesson. Every router file declares its auth
posture once at the ``APIRouter(...)`` level and inherits to every
endpoint. Auth dependencies live in ``http/dependencies.py``;
routes call into the corresponding ``api/`` module.
"""
