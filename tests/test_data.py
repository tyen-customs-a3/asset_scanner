from pathlib import Path

# Define root path for sample data
SAMPLE_DATA_ROOT = Path(__file__).parent.parent / "sample_data"

MIRRORFORM_PBO_FILE = SAMPLE_DATA_ROOT / '@tc_mirrorform/addons/mirrorform.pbo'
BABE_EM_PBO_FILE = SAMPLE_DATA_ROOT / '@em/addons/babe_em.pbo'
HEADBAND_PBO_FILE = SAMPLE_DATA_ROOT / '@tc_rhs_headband/addons/rhs_headband.pbo'

# PBO path constants
PBO_PATHS = {
    'babe_em.pbo': BABE_EM_PBO_FILE,
    'mirrorform.pbo': MIRRORFORM_PBO_FILE,
    'rhs_headband.pbo': HEADBAND_PBO_FILE
}

EM_BABE_EXPECTED = {
    'models/helper.p3d',
    'data/nope_ca.paa',
    'textures/EM_ca.paa',
    'textures/ui/fatigue_ca.paa',
    'animations/climbOnHer_pst.rtm',
    'animations/climbOnHer_rfl.rtm',
    'animations/climbOnHer_ua.rtm',
    'animations/climbOnH_pst.rtm',
    'animations/climbOnH_rfl.rtm',
    'animations/climbOnH_ua.rtm',
    'animations/climbOn_pst.rtm',
    'animations/climbOn_rfl.rtm',
    'animations/climbOn_ua.rtm',
    'animations/climbOverHer_pst.rtm',
    'animations/climbOverHer_rfl.rtm',
    'animations/climbOverHer_ua.rtm',
    'animations/climbOverH_pst.rtm',
    'animations/climbOverH_rfl.rtm',
    'animations/climbOverH_ua.rtm',
    'animations/climbOver_pst.rtm',
    'animations/climbOver_rfl.rtm',
    'animations/climbOver_ua.rtm',
    'animations/drop_pst.rtm',
    'animations/drop_rfl.rtm',
    'animations/drop_ua.rtm',
    'animations/jump_pst.rtm',
    'animations/jump_rfl.rtm',
    'animations/jump_ua.rtm',
    'animations/pull.rtm',
    'animations/push.rtm',
    'animations/stepOn_pst.rtm',
    'animations/stepOn_rfl.rtm',
    'animations/stepOn_ua.rtm',
    'animations/vaultover_pst.rtm',
    'animations/vaultover_rfl.rtm',
    'animations/vaultover_ua.rtm'
}

MIRROR_EXPECTED = {
    "logo.paa",
    "logo_small.paa",
    "uniform/mirror.p3d",
    "uniform/black.paa"
}

HEADBAND_EXPECTED = {
    "data/tex/headband_choccymilk_co.paa",
    "logo.paa",
    "logo_small.paa"
}

# Expected path structure mapping
EXPECTED_PATHS = {
    'babe_em.pbo': EM_BABE_EXPECTED,
    'mirrorform.pbo': MIRROR_EXPECTED,
    'rhs_headband.pbo': HEADBAND_EXPECTED
}

# Add source mapping for verification
SOURCE_MAPPING = {
    'babe_em.pbo': 'em',
    'mirrorform.pbo': 'tc_mirrorform',
    'rhs_headband.pbo': 'tc_rhs_headband'
}

# PBO test data
PBO_FILES = {
    'babe_em.pbo': {
        'prefix': 'babe/babe_em',
        'assets': EM_BABE_EXPECTED
    },
    'mirrorform.pbo': {
        'prefix': 'tc/mirrorform',
        'assets': MIRROR_EXPECTED
    },
    'rhs_headband.pbo': {
        'prefix': 'tc/rhs_headband',
        'assets': HEADBAND_EXPECTED
    }
}
