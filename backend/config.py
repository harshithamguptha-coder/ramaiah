"""Runtime configuration for the Q-Compass backend.

Every value can be overridden with an environment variable so the same code
runs locally, in Docker, or in CI without edits.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from the environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Q-Compass API"
    app_version: str = "0.1.0"
    environment: str = "development"

    # Comma-separated list of origins allowed to call the API.
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:4173,http://127.0.0.1:4173"
    )

    upload_dir: str = "uploads"
    max_upload_bytes: int = 25 * 1024 * 1024  # 25 MB
    allowed_extensions: tuple[str, ...] = (".csv", ".xlsx", ".json")

    # How many analyses to keep in the in-memory store before evicting the oldest.
    store_max_items: int = 50

    # Simulated per-stage latency (seconds) so the UI progress states are visible.
    simulate_pipeline_delay: float = 0.35

    # ------------------------------------------------------------------
    # Analysis engine budgets.
    #
    # Every value here is a *bound*, not a preference. The engine must finish a
    # request in predictable wall-clock time on a laptop, so it samples large
    # data and uses deliberately cheap estimators rather than tuning hard.
    # ------------------------------------------------------------------
    # Rows read from disk for profiling. Anything larger is sampled.
    analysis_max_rows: int = 20_000
    # Rows actually handed to model fitting / cross-validation.
    analysis_max_train_rows: int = 20_000
    # Columns kept for model fitting after dropping constant / all-null ones.
    analysis_max_features: int = 400
    # Random-forest budget (kept small on purpose - we want a baseline, not a win).
    analysis_forest_trees: int = 200
    # 0 means "let the estimator decide".
    analysis_forest_max_depth: int = 12
    analysis_forest_min_samples_leaf: int = 2
    # Cross-validation folds. 0 or 1 disables CV in favour of a single hold-out.
    analysis_cv_folds: int = 3
    # An RBF SVM costs O(n^2*d); only attempt it below these limits.
    analysis_svm_max_rows: int = 5_000
    analysis_svm_max_features: int = 200
    # Largest per-class share that still counts as a usable train/test split.
    analysis_min_class_count: int = 5
    # Seed for every sampler and estimator, so a given file always gives the
    # same numbers (reproducible demos and stable tests).
    analysis_random_seed: int = 42
    # Correlation / redundancy pass is O(d^2); cap the matrix size.
    analysis_max_corr_features: int = 200
    analysis_correlation_threshold: float = 0.95
    # Columns whose distinct-value count exceeds this share of the row count are
    # reported as high-cardinality (id-like) and are poor encoding candidates.
    analysis_high_cardinality_ratio: float = 0.5

    # ------------------------------------------------------------------
    # Quantum suitability engine.
    # ------------------------------------------------------------------
    # Qubit budget assumed addressable by publicly available devices. Used as
    # the denominator of the hardware-feasibility factor - it is a *published
    # capability reference*, not a claim about any particular QPU.
    quantum_reference_qubits: int = 127
    # Feature count above which angle encoding is treated as out of reach.
    quantum_encoding_feature_ceiling: int = 64
    # Row count above which shot-based quantum training is treated as out of reach.
    quantum_sample_ceiling: int = 10_000
    # Candidate quantum methods surfaced in the response.
    quantum_max_methods: int = 4

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
