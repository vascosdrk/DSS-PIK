# flake8: noqa
from . import climdex, rai, knmi, dist, plot, si, utils, model_selection
from ._version import __version__, show_versions
from .si import SI, sgi, spei, spi, ssfi, ssmi, generate_nan_diagnostic_summary
from .utils import (
    dasarian_windows,
    is_dasarian_index,
    is_valid_dasarian_labels,
    to_dasarian,
    to_dekad,
    daily_to_dasarian,
    rolling_dasarian,
    rolling_dekad,
    get_expected_dasarian_days,
    canonical_dasarian_calendar,
    dasarian_window_group_yearly_df,
    monthly_windows,
    MONTHLY_WINDOWS,
    is_monthly_index,
    is_valid_monthly_labels,
    to_monthly,
    to_month,
    daily_to_monthly,
    daily_to_month,
    rolling_monthly,
    rolling_month,
    get_expected_month_days,
    canonical_monthly_calendar,
)

from .model_selection import (
    select_best_distribution,
    select_models_by_group,
    summarize_candidate_diagnostics,
    rank_aggregated_candidates,
)

