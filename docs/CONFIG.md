# Config

Adding another revanced app is as easy as this:

```toml
[Some-App]
apkmirror-dlurl = "https://www.apkmirror.com/apk/inc/app"
# or uptodown-dlurl = "https://app.en.uptodown.com/android"
```

## More about other options

There exists an example below with all defaults shown and all the keys
explicitly set.

**All keys are optional** (except download urls) and are assigned to their
default values if not set explicitly.

```toml
parallel-jobs = 1                    # amount of cores to use for parallel patching, if not set $(nproc) is used
compression-level = 9                # module zip compression level
remove-rv-integrations-checks = true # remove checks from the revanced integrations
# Multiple patch sources can be specified as an array (patches are merged, later sources override earlier ones on conflicts).
# The default is Morphe (MorpheApp/morphe-patches + MorpheApp/morphe-cli).
patches-source = [
  "MorpheApp/morphe-patches",       # default Morphe patches
  "jkennethcarino/adobo",           # Morphe-compatible add-on patches (run on Morphe CLI)
  # "brosssh/revanced-external-bundles",         # resolves via the external-bundles aggregator (matched by package id)
  # "external-bundles:revanced-patches"          # explicit bundle_type selector
]
# Single source still works for backwards compatibility:
# patches-source = "MorpheApp/morphe-patches"
cli-source = "MorpheApp/morphe-cli"             # where to fetch CLI from. default: "MorpheApp/morphe-cli"
# Supported CLI flavors (auto-detected from `java -jar <cli> --help`):
#   - "revanced-cli-v5"   ReVanced CLI v5 (long flags, `--patch`, `--input`)
#   - "revanced-cli-v6"   ReVanced CLI v6 (short flags, `-e`, `-i`)
#   - "morphe-cli"        Morphe CLI (long flags, `--patch`, `--input`)
#   - "adobo-cli"         Adobo CLI (Morphe-compatible flag set)
# Force a specific profile with cli-profile (default "auto"). Auto-detection
# inspects `--help` and falls back to ReVanced CLI v5 on uncertainty.
cli-profile = "auto"
# options like cli-source can also set per app
rv-brand = "Morphe" # rebrand from 'Morphe' to something different. default: "Morphe"
patches-version = "latest" # 'latest', 'dev', or a version number. default: "latest"
cli-version = "latest"     # 'latest', 'dev', or a version number. default: "latest"
[Some-App]
app-name = "SomeApp" # if set, release name becomes SomeApp instead of Some-App. default is same as table name, which is 'Some-App' here.
enabled = true       # whether to build the app. default: true
build-mode = "apk"   # 'both', 'apk' or 'module'. default: apk
# 'auto' option gets the latest possible version supported by all the included patches
# 'latest' gets the latest stable without checking patches support. 'beta' gets the latest beta/alpha
# whitespace seperated list of patches to exclude. default: ""
version = "auto"     # 'auto', 'latest', 'beta' or a version number (e.g. '17.40.41'). default: auto
# optional args to be passed to cli. can be used to set patch options
# must be a TOML array of strings
patcher-args = [
  "-OdarkThemeBackgroundColor=#FF0F0F0F",
  "-Oanother-option=value"
]
excluded-patches = """\
  'Some Patch' \
  'Some Other Patch' \
  """
included-patches = "'Some Patch'"                          # whitespace seperated list of non-default patches to include. default: ""
include-stock = true                                       # includes stock apk in the module. default: true
exclusive-patches = false                                  # exclude all patches by default. default: false
apkmirror-dlurl = "https://www.apkmirror.com/apk/inc/app"
uptodown-dlurl = "https://spotify.en.uptodown.com/android"
module-prop-name = "some-app-magisk"                       # magisk module prop name.
apkmirror-dpi = "360-480dpi"                               # used to select apk variant from apkmirror. default: nodpi
arch = "arm64-v8a"                                         # 'arm64-v8a', 'arm-v7a', 'all', 'both'. 'both' downloads both arm64-v8a and arm-v7a. default: all
riplib = true                                              # enables stripping the other ABI's .so files from APKs. default: true

# ============================================================================
# Patch sources reference
# ============================================================================
# Morphe (default):      MorpheApp/morphe-patches     + MorpheApp/morphe-cli
# ReVanced:              ReVanced/revanced-patches    + ReVanced/revanced-cli
# ReVanced Extended:     anddea/revanced-patches      + inotia00/revanced-cli
# Adobo (Morphe-compat): jkennethcarino/adobo        + MorpheApp/morphe-cli
# Piko (Twitter/X):      crimera/piko                 + (ReVanced/Morphe CLI)
# Patcheddit (Reddit):   wchill/patcheddit            + (ReVanced/Morphe CLI)
# External bundles:      brosssh/revanced-external-bundles (or `external-bundles:<bundle_type>`)
```
