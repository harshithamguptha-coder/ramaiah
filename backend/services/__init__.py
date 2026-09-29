"""Service layer: one module per pipeline stage, plus the orchestrator.

Each stage exposes a pure function that takes context and returns a dict. They
share nothing but the context object, so a stage can be replaced by a real
implementation (scikit-learn, Qiskit, PennyLane, ...) without touching its
neighbours or the routes.
"""
