#!/usr/bin/env bash
# shellcheck enable=all shell=bash source-path=SCRIPTDIR external-sources=true
set -euo pipefail; shopt -s nullglob globstar
export LC_ALL=C; IFS=$'\n\t'
has(){ command -v -- "$1" &>/dev/null; }

CWD=$(pwd)
TEMP_DIR="temp"
BIN_DIR="bin"
BUILD_DIR="build"
OS=$(uname -o 2>/dev/null || uname -s)
GH_HEADER=""
[[ -n "${GITHUB_TOKEN-}" ]] && GH_HEADER="Authorization: token ${GITHUB_TOKEN}"
LIB_DIR="${CWD}/lib"

source "${LIB_DIR}/logger.sh"
source "${LIB_DIR}/network.sh"
source "${LIB_DIR}/helpers.sh"

install_pkg(){
  local cmd=$1 pkg=${2:-$1}
  has "$cmd" && return 0
  pr "Installing $pkg..."
  if   has pkg;     then pkg install -y "$pkg"
  elif has apt-get; then sudo apt-get install -y "$pkg"
  elif has dnf;     then sudo dnf install -y "$pkg"
  elif has yum;     then sudo yum install -y "$pkg"
  elif has pacman;  then sudo pacman -S --noconfirm "$pkg"
  elif has apk;     then sudo apk add "$pkg"
  else abort "Cannot auto-install $pkg. Please install it manually."
  fi
  has "$cmd" || abort "Failed to install $pkg"
}
toml_prep(){
  [ -f "$1" ] || return 1
  if [ "${1##*.}" = toml ]; then
    __TOML__=$($TOML --output json --file "$1" .)
  elif [ "${1##*.}" = json ]; then
    __TOML__=$(cat "$1")
  else abort "config extension not supported"; fi
}
toml_get_table_names(){ jq -r -e 'to_entries[] | select(.value|type=="object")|.key' <<<"$__TOML__"; }
toml_get_table_main(){ jq -r -e 'to_entries|map(select(.value|type!="object"))|from_entries' <<<"$__TOML__"; }
toml_get_table(){ jq -r -e ".\"${1}\"" <<<"$__TOML__"; }
toml_get(){
  local op; op=$(jq -r ".\"${2}\"|values" <<<"$1")
  if [ -n "$op" ]; then
    op="${op#"${op%%[![:space:]]*}"}"; op="${op%"${op##*[![:space:]]}"}"; op=${op//"'"/'"'}
    printf '%s\n' "$op"
  else return 1; fi
}
get_rv_prebuilts(){
  local cli_src=$1 cli_ver=$2 patches_src=$3 patches_ver=$4
  pr "Getting prebuilts (${patches_src%/*})" >&2
  local cl_dir=${TEMP_DIR}/${patches_src%/*}; cl_dir=${cl_dir,,}-rv; mkdir -p "$cl_dir"
  local out_files=()
  for spec in "$cli_src CLI $cli_ver revanced-cli" "$patches_src Patches $patches_ver patches"; do
    set -- $spec; local src=$1 tag=$2 ver=${3-} fprefix=$4 ext grab_cl=false
    if [ "$tag" = "CLI" ]; then ext=jar; grab_cl=false
    else ext=rvp; grab_cl=true; fi
    local dir=${TEMP_DIR}/${src%/*}; dir=${dir,,}-rv; mkdir -p "$dir"
    local rv_rel="https://api.github.com/repos/${src}/releases" name_ver
    if [ "$ver" = "dev" ]; then
      local resp; resp=$(gh_req "$rv_rel" -) || return 1
      ver=$(jq -e -r '.[]|.tag_name' <<<"$resp" | get_highest_ver) || return 1
    fi
    if [ "$ver" = "latest" ]; then rv_rel+="/latest"; name_ver="*"; else rv_rel+="/tags/${ver}"; name_ver="$ver"; fi
    local file tag_name name url
    file=$(find "$dir" -name "${fprefix}-${name_ver#v}.${ext}" -type f 2>/dev/null | head -1 || true)
    if [ -z "$file" ]; then
      local resp asset; resp=$(gh_req "$rv_rel" -) || return 1
      tag_name=$(jq -r '.tag_name' <<<"$resp")
      asset=$(jq -e -r ".assets[]|select(.name|endswith(\"$ext\"))" <<<"$resp") || return 1
      url=$(jq -r .url <<<"$asset"); name=$(jq -r .name <<<"$asset")
      file="${dir}/${name}"
      gh_dl "$file" "$url" >&2 || return 1
      printf "> ⚙️ » %s/%s  \n" "$(cut -d/ -f1 <<<"$src")" "$name" >>"${cl_dir}/changelog.md"
    else
      grab_cl=false; name=$(basename "$file"); tag_name=$(cut -d'-' -f3- <<<"$name"); tag_name=v${tag_name%.*}
    fi
    if [ "$tag" = "Patches" ] && [ "$grab_cl" = true ]; then printf "[🔗 » Changelog](https://github.com/%s/releases/tag/%s)\n\n" "$src" "$tag_name" >>"${cl_dir}/changelog.md"; fi
    out_files+=("$file")
  done
  printf '%s %s\n' "${out_files[0]}" "${out_files[1]}"
}
merge_splits(){
  local bundle=$1 output=$2
  pr "Merging splits"
  gh_dl "$TEMP_DIR/apkeditor.jar" "https://github.com/REAndroid/APKEditor/releases/download/V1.4.5/APKEditor-1.4.5.jar" >/dev/null || return 1
  if ! OP=$(java -jar "$TEMP_DIR/apkeditor.jar" merge -i "${bundle}" -o "${bundle}.mzip" -clean-meta -f 2>&1); then epr "Apkeditor ERROR: $OP"; return 1; fi
  mkdir "${bundle}-zip"
  unzip -qo "${bundle}.mzip" -d "${bundle}-zip"
  (cd "${bundle}-zip" && zip -0rq "${CWD}/${bundle}.zip" .)
  cp "${bundle}.zip" "${output}"
  rm -rf "${bundle}-zip" "${bundle}.zip" "${bundle}.mzip" || :
}
# apkmirror helpers
apk_mirror_search(){
  local resp=$1 dpi=$2 arch=$3 apk_bundle=$4
  local apparch dlurl node app_table
  if [ "$arch" = all ]; then apparch=(universal noarch 'arm64-v8a + armeabi-v7a'); else apparch=("$arch" universal noarch 'arm64-v8a + armeabi-v7a'); fi
  for ((n=1;n<40;n++)); do
    node=$($HTMLQ "div.table-row.headerFont:nth-last-child($n)" -r "span:nth-child(n+3)" <<<"$resp") || true
    [ -z "$node" ] && break
    app_table=$($HTMLQ --text --ignore-whitespace <<<"$node")
    if [ "$(sed -n 3p <<<"$app_table")" = "$apk_bundle" ] && [ "$(sed -n 6p <<<"$app_table")" = "$dpi" ] && isoneof "$(sed -n 4p <<<"$app_table")" "${apparch[@]}"; then
      dlurl=$($HTMLQ --base https://www.apkmirror.com --attribute href "div:nth-child(1)>a:nth-child(1)" <<<"$node")
      echo "$dlurl"; return 0
    fi
  done; return 1
}
dl_apkmirror(){
  local url=$1 version=${2// /-} output=$3 arch=$4 dpi=$5 is_bundle=false
  if [ -f "${output}.apkm" ]; then is_bundle=true
  else
    [ "$arch" = "arm-v7a" ] && arch="armeabi-v7a"
    local resp node apkmname dlurl=""
    apkmname=$($HTMLQ "h1.marginZero" --text <<<"$__APKMIRROR_RESP__"); apkmname=${apkmname,,}; apkmname=${apkmname// /-}; apkmname=${apkmname//[^a-z0-9-]/}
    url="${url}/${apkmname}-${version//./-}-release/"
    resp=$(req "$url" -) || return 1
    node=$($HTMLQ "div.table-row.headerFont:nth-last-child(1)" -r "span:nth-child(n+3)" <<<"$resp") || true
    if [ -n "$node" ]; then
      if ! dlurl=$(apk_mirror_search "$resp" "$dpi" "$arch" "APK"); then
        if ! dlurl=$(apk_mirror_search "$resp" "$dpi" "$arch" "BUNDLE"); then return 1; else is_bundle=true; fi
      fi
      resp=$(req "$dlurl" -) || return 1
    fi
    url=$(echo "$resp" | $HTMLQ --base https://www.apkmirror.com --attribute href "a.btn") || return 1
    url=$(req "$url" - | $HTMLQ --base https://www.apkmirror.com --attribute href "span>a[rel = nofollow]") || return 1
  fi
  if [ "$is_bundle" = true ]; then req "$url" "${output}.apkm" || return 1; merge_splits "${output}.apkm" "${output}"
  else req "$url" "${output}" || return 1; fi
}
get_apkmirror_vers(){
  local apkm_resp vers
  apkm_resp=$(req "https://www.apkmirror.com/uploads/?appcategory=${__APKMIRROR_CAT__}" -)
  vers=$(sed -n 's;.*Version:</span><span class="infoSlide-value">\(.*\) </span>.*;\1;p' <<<"$apkm_resp" | awk '{$1=$1}1')
  if [ "${__AAV__:-false}" = false ]; then
    local r_vers=() v; vers=$(grep -iv "\(beta\|alpha\)" <<<"$vers")
    while IFS= read -r v; do grep -iq "${v} \(beta\|alpha\)" <<<"$apkm_resp" || r_vers+=("$v"); done <<<"$vers"
    printf '%s\n' "${r_vers[@]}"
  else printf '%s\n' "$vers"; fi
}
get_apkmirror_pkg_name(){ sed -n 's;.*id=\(.*\)" class="accent_color.*;\1;p' <<<"$__APKMIRROR_RESP__"; }
get_apkmirror_resp(){ __APKMIRROR_RESP__=$(req "$1" -); __APKMIRROR_CAT__="${1##*/}"; }
# uptodown helpers
get_uptodown_resp(){ __UPTODOWN_RESP__=$(req "${1}/versions" -); __UPTODOWN_RESP_PKG__=$(req "${1}/download" -); }
get_uptodown_vers(){ $HTMLQ --text ".version" <<<"$__UPTODOWN_RESP__"; }
get_uptodown_pkg_name(){ $HTMLQ --text "tr.full:nth-child(1)>td:nth-child(3)" <<<"$__UPTODOWN_RESP_PKG__"; }
dl_uptodown(){
  local uptodown_dlurl=$1 version=$2 output=$3 arch=$4 dpi_unused=$5
  [ "$arch" = "arm-v7a" ] && arch="armeabi-v7a"
  local apparch; if [ "$arch" = all ]; then apparch=('arm64-v8a, armeabi-v7a, x86, x86_64' 'arm64-v8a, armeabi-v7a'); else apparch=("$arch" 'arm64-v8a, armeabi-v7a, x86, x86_64' 'arm64-v8a, armeabi-v7a'); fi
  local op resp data_code versionURL="" is_bundle=false
  data_code=$($HTMLQ "#detail-app-name" --attribute data-code <<<"$__UPTODOWN_RESP__")
  for i in {1..5}; do
    resp=$(req "${uptodown_dlurl}/apps/${data_code}/versions/${i}" -)
    if ! op=$(jq -e -r ".data|map(select(.version==\"${version}\"))|.[0]" <<<"$resp"); then continue; fi
    [ "$(jq -e -r '.kindFile' <<<"$op")" = "xapk" ] && is_bundle=true
    versionURL=$(jq -e -r '.url + "/" + .extraURL + "/" + (.versionID|tostring)' <<<"$(jq -r '.versionURL' <<<"$op")") || return 1
    break
  done
  [ -z "$versionURL" ] && return 1
  resp=$(req "$versionURL" -) || return 1
  local data_version files node_arch data_file_id
  data_version=$($HTMLQ '.button.variants' --attribute data-version <<<"$resp") || true
  if [ -n "$data_version" ]; then
    files=$(req "${uptodown_dlurl%/*}/app/${data_code}/version/${data_version}/files" - | jq -e -r .content) || return 1
    for ((n=1;n<12;n+=2)); do
      node_arch=$($HTMLQ ".content>p:nth-child($n)" --text <<<"$files" | xargs) || true
      [ -z "$node_arch" ] && return 1
      isoneof "$node_arch" "${apparch[@]}" || continue
      data_file_id=$($HTMLQ "div.variant:nth-child($((n+1)))>.v-report" --attribute data-file-id <<<"$files") || return 1
      resp=$(req "${uptodown_dlurl}/download/${data_file_id}-x" -); break
    done
  fi
  local data_url; data_url=$($HTMLQ "#detail-download-button" --attribute data-url <<<"$resp") || return 1
  if [ "$is_bundle" = true ]; then req "https://dw.uptodown.com/dwn/${data_url}" "$output.apkm" || return 1; merge_splits "${output}.apkm" "${output}"
  else req "https://dw.uptodown.com/dwn/${data_url}" "$output"; fi
}
# archive helpers
get_archive_resp(){
  local r; r=$(req "$1" -) || return 1
  __ARCHIVE_RESP__=$(sed -n 's;^<a href="\(.*\)"[^"]*;\1;p' <<<"$r")
  __ARCHIVE_PKG_NAME__=$(awk -F/ '{print $NF}' <<<"$1")
}
get_archive_vers(){ sed 's/^[^-]*-//;s/-\(all\|arm64-v8a\|arm-v7a\)\.apk//g' <<<"$__ARCHIVE_RESP__"; }
get_archive_pkg_name(){ echo "$__ARCHIVE_PKG_NAME__"; }
dl_archive(){
  local url=$1 version=$2 output=$3 arch=$4 version_f=${version// /}
  local path; path=$(grep "${version_f#v}-${arch// /}" <<<"$__ARCHIVE_RESP__") || return 1
  req "${url}/${path}" "$output"
}
list_args(){ tr -d '\t\r' <<<"$1" | tr -s ' ' | sed 's/" "/"\n"/g' | sed "s/\([^\"]\)\"\([^\"]\)/\1'\''\2/g" | grep -v '^$' || :; }
join_args(){ list_args "$1" | sed "s/^/${2} /" | paste -sd " " - || :; }
get_patch_last_supported_ver(){
  local list_patches=$1 pkg_name=$2 inc_sel=$3 _exc_sel=$4 _exclusive=$5
  local op
  if [ -n "$inc_sel" ]; then
    op=$(awk '{$1=$1}1' <<<"$list_patches") || { epr "list-patches: '$op'"; return 1; }
    local vers="" ver NL=$'\n'
    while IFS= read -r line; do
      line="${line:1:${#line}-2}"
      ver=$(sed -n "/^Name: $line\$/,/^\$/p" <<<"$op" | sed -n "/^Compatible versions:\$/,/^\$/p" | tail -n +2)
      vers+="${ver}${NL}"
    done <<<"$(list_args "$inc_sel")"
    vers=$(awk '{$1=$1}1' <<<"$vers")
    [ -n "$vers" ] && { get_highest_ver <<<"$vers"; return; }
  fi
  op=$(java -jar "$rv_cli_jar" list-versions "$rv_patches_jar" -f "$pkg_name" 2>&1 | tail -n +3 | awk '{$1=$1}1') || { epr "list-versions: '$op'"; return 1; }
  [[ "$op" = "Any" ]] && return 0
  local pcount; pcount=$(head -1 <<<"$op"); pcount=${pcount#*(}; pcount=${pcount% *}
  [[ -z "$pcount" ]] && abort "unreachable: '$pcount'"
  grep -F "($pcount patch" <<<"$op" | sed 's/ (.* patch.*//' | get_highest_ver || return 1
}
patch_apk(){
  local stock_input=$1 patched_apk=$2 patcher_args_str=$3 rv_cli_jar=$4 rv_patches_jar=$5
  local args=()
  IFS=' ' read -r -a args <<<"$patcher_args_str"
  local cmd=(env -u GITHUB_REPOSITORY java -jar "$rv_cli_jar" patch "$stock_input" --purge -o "$patched_apk" -p "$rv_patches_jar" --keystore=ks.keystore --keystore-entry-password=r4nD0M.paS4W0rD --keystore-password=r4nD0M.paS4W0rD --signer=krvstek --keystore-entry-alias=krvstek)
  if [ "$OS" = "Android" ]; then cmd+=("--custom-aapt2-binary=${AAPT2}"); fi
  cmd+=("${args[@]}")
  pr "${cmd[*]}"
  if ! "${cmd[@]}"; then rm -f "$patched_apk" || :; return 1; fi
  [[ -f "$patched_apk" ]]
}
check_sig(){
  local file=$1 pkg_name=$2 sig
  if grep -q "$pkg_name" sig.txt 2>/dev/null; then
    sig=$(java -jar "$APKSIGNER" verify --print-certs "$file" | grep ^Signer | grep SHA-256 | tail -1 | awk '{print $NF}')
    echo "$pkg_name signature: ${sig}"
    grep -qFx "$sig $pkg_name" sig.txt
  fi
}
build_rv(){
  eval "declare -A args=${1#*=}"  # only for local scope (kept; safe because input is ours)
  local version="" pkg_name="" version_mode=${args[version]} app_name=${args[app_name]} table=${args[table]} dl_from=${args[dl_from]} arch=${args[arch]}
  local arch_f=${arch// /} app_name_l=${app_name,,}; app_name_l=${app_name_l// /-}
  local p_patcher_args=()
  [ -n "${args[excluded_patches]}" ] && p_patcher_args+=("$(join_args "${args[excluded_patches]}" -d)")
  [ -n "${args[included_patches]}" ] && p_patcher_args+=("$(join_args "${args[included_patches]}" -e)")
  [ "${args[exclusive_patches]}" = true ] && p_patcher_args+=("--exclusive")
  local tried_dl=()
  for dl_p in archive apkmirror uptodown; do
    [ -z "${args[${dl_p}_dlurl]}" ] && continue
    if get_${dl_p}_resp "${args[${dl_p}_dlurl]}" && pkg_name=$(get_"${dl_p}"_pkg_name); then dl_from=$dl_p; tried_dl+=("$dl_p"); break; fi
    args[${dl_p}_dlurl]="" ; epr "ERROR: Could not find ${table} in ${dl_p}"
  done
  [ -z "$pkg_name" ] && { epr "empty pkg name, not building ${table}."; return 0; }
  local list_patches; list_patches=$(java -jar "$rv_cli_jar" list-patches "$rv_patches_jar" -f "$pkg_name" -v -p 2>&1)
  local get_latest_ver=false
  if [ "$version_mode" = auto ]; then
    if ! version=$(get_patch_last_supported_ver "$list_patches" "$pkg_name" "${args[included_patches]}" "${args[excluded_patches]}" "${args[exclusive_patches]}"); then exit 1; elif [ -z "$version" ]; then get_latest_ver=true; fi
  elif isoneof "$version_mode" latest beta; then get_latest_ver=true; p_patcher_args+=("-f")
  else version=$version_mode; p_patcher_args+=("-f"); fi
  if [ "$get_latest_ver" = true ]; then [ "$version_mode" = beta ] && __AAV__=true || __AAV__=false; version=$(get_"${dl_from}"_vers | get_highest_ver)
  fi
  [[ -z "$version" ]] && { epr "empty version, not building ${table}."; return 0; }
  pr "Choosing version '${version}' for ${table}"
  local version_f=${version// /}; version_f=${version_f#v}
  local stock_apk="${TEMP_DIR}/${pkg_name}-${version_f}-${arch_f}.apk"
  if [ ! -f "$stock_apk" ]; then
    for dl_p in archive apkmirror uptodown; do
      [ -z "${args[${dl_p}_dlurl]}" ] && continue
      pr "Downloading '${table}' from ${dl_p}"
      if ! isoneof "$dl_p" "${tried_dl[@]}"; then get_${dl_p}_resp "${args[${dl_p}_dlurl]}"; fi
      if dl_${dl_p} "${args[${dl_p}_dlurl]}" "$version" "$stock_apk" "$arch" "${args[dpi]}" "$get_latest_ver"; then break; fi
      epr "ERROR: Could not download '${table}' from ${dl_p} with version '${version}', arch '${arch}', dpi '${args[dpi]}'"
    done
    [ -f "$stock_apk" ] || return 0
  fi
  if ! OP=$(check_sig "$stock_apk" "$pkg_name" 2>&1) && ! grep -qFx "ERROR: Missing META-INF/MANIFEST.MF" <<<"$OP"; then epr "$pkg_name not building, apk signature mismatch '$stock_apk': $OP"; return 0; fi
  log "🟢 » ${table}: \`${version}\`"
  local microg_patch; microg_patch=$(grep "^Name: " <<<"$list_patches" | grep -i "gmscore\|microg" || :) ; microg_patch=${microg_patch#*: }
  if [ -n "$microg_patch" ] && [[ ${p_patcher_args[*]} =~ $microg_patch ]]; then epr "You can't include/exclude microg patch manually."; p_patcher_args=("${p_patcher_args[@]//-[ei] ${microg_patch}/}"); fi
  local version_code_patch; version_code_patch=$(grep "^Name: " <<<"$list_patches" | grep -i "change version code" || :) ; version_code_patch=${version_code_patch#*: }
  if [ -n "$version_code_patch" ] && [[ ${p_patcher_args[*]} =~ $version_code_patch ]]; then epr "You can't include/exclude version code patch manually."; p_patcher_args=("${p_patcher_args[@]//-[ei] ${version_code_patch}/}"); fi
  local patcher_args=("${p_patcher_args[@]}")
  [ -n "${args[patcher_args]}" ] && patcher_args+=("${args[patcher_args]}")
  [ -n "$microg_patch" ] && patcher_args+=("-e \"${microg_patch}\"")
  [ -n "$version_code_patch" ] && patcher_args+=("-e \"${version_code_patch}\"")
  if [ "${args[riplib]}" = true ]; then
    patcher_args+=("--rip-lib x86_64 --rip-lib x86")
    if [ "$arch" = "arm64-v8a" ]; then patcher_args+=("--rip-lib armeabi-v7a"); elif [ "$arch" = "arm-v7a" ]; then patcher_args+=("--rip-lib arm64-v8a"); fi
  fi
  local rv_brand_f=${args[rv_brand],,}; rv_brand_f=${rv_brand_f// /-}
  local patched_apk="${TEMP_DIR}/${app_name_l}-${rv_brand_f}-${version_f}-${arch_f}.apk"
  if [ "${NORB:-}" != true ] || [ ! -f "$patched_apk" ]; then
    if ! patch_apk "$stock_apk" "$patched_apk" "${patcher_args[*]}" "${args[cli]}" "${args[ptjar]}"; then epr "Building '${table}' failed!"; return 0; fi
  fi
  local apk_output="${BUILD_DIR}/${app_name_l}-${rv_brand_f}-v${version_f}-${arch_f}.apk"
  mv -f "$patched_apk" "$apk_output"
  pr "Built ${table}: '${apk_output}'"
}
vtf(){ isoneof "$1" true false || abort "ERROR: '$1' is not valid for '$2': only true/false"; }
main(){
  trap "rm -rf $TEMP_DIR/*tmp.* $TEMP_DIR/*/*tmp.* $TEMP_DIR/*-temporary-files; exit 130" INT
  if [ "${1-}" = "clean" ]; then rm -rf "$TEMP_DIR" "$BUILD_DIR" logs build.md; exit 0; fi
  mkdir -p "$TEMP_DIR" "$BUILD_DIR"
  install_pkg jq
  if [ "$OS" = "Android" ]; then
    install_pkg java openjdk-17
    if [ ! -d "$HOME/storage" ]; then pr "Requesting Termux storage permission..."; pr "Please allow storage access in the popup"; sleep 5; termux-setup-storage; fi
    OUTPUT_DIR="/sdcard/Download/rvx-output"; mkdir -p "$OUTPUT_DIR"
  else
    install_pkg java openjdk-21-jdk
    OUTPUT_DIR="$BUILD_DIR"
  fi
  install_pkg zip
  set_prebuilts
  local cfg="${1:-config.toml}"
  toml_prep "$cfg" || abort "could not find config file '$cfg'\n\tUsage: $0 <config.toml>"
  local main_config_t; main_config_t=$(toml_get_table_main)
  local PARALLEL_JOBS; PARALLEL_JOBS=$(toml_get "$main_config_t" parallel-jobs || true)
  if [ -z "${PARALLEL_JOBS:-}" ]; then [ "$OS" = "Android" ] && PARALLEL_JOBS=1 || PARALLEL_JOBS=$(nproc); fi
  DEF_PATCHES_VER=$(toml_get "$main_config_t" patches-version || printf 'latest')
  DEF_CLI_VER=$(toml_get "$main_config_t" cli-version || printf 'latest')
  DEF_PATCHES_SRC=$(toml_get "$main_config_t" patches-source || printf 'anddea/revanced-patches')
  DEF_CLI_SRC=$(toml_get "$main_config_t" cli-source || printf 'inotia00/revanced-cli')
  DEF_RV_BRAND=$(toml_get "$main_config_t" rv-brand || printf 'ReVanced Extended')
  : >build.md
  [ -e "$TEMP_DIR"/*-rv/changelog.md ] && : >"$TEMP_DIR"/*-rv/changelog.md || true
  declare -A cliriplib; local idx=0
  for table_name in $(toml_get_table_names); do
    [ -z "$table_name" ] && continue
    local t; t=$(toml_get_table "$table_name")
    local enabled; enabled=$(toml_get "$t" enabled || printf 'true'); vtf "$enabled" "enabled"; [ "$enabled" = false ] && continue
    ((idx >= PARALLEL_JOBS)) && { wait -n; idx=$((idx-1)); }
    declare -A app_args
    local patches_src; patches_src=$(toml_get "$t" patches-source || printf '%s' "$DEF_PATCHES_SRC")
    local patches_ver; if [ "${BUILD_MODE:-}" = "dev" ]; then patches_ver="dev"; else patches_ver=$(toml_get "$t" patches-version || printf '%s' "$DEF_PATCHES_VER"); fi
    local cli_src; cli_src=$(toml_get "$t" cli-source || printf '%s' "$DEF_CLI_SRC")
    local cli_ver; cli_ver=$(toml_get "$t" cli-version || printf '%s' "$DEF_CLI_VER")
    local RVP; RVP="$(get_rv_prebuilts "$cli_src" "$cli_ver" "$patches_src" "$patches_ver")" || abort "could not download rv prebuilts"
    read -r rv_cli_jar rv_patches_jar <<<"$RVP"
    app_args[cli]=$rv_cli_jar; app_args[ptjar]=$rv_patches_jar
    if [[ -v cliriplib[${app_args[cli]}] ]]; then app_args[riplib]=${cliriplib[${app_args[cli]}]}
    else
      if [[ $(java -jar "${app_args[cli]}" patch 2>&1) == *rip-lib* ]]; then cliriplib[${app_args[cli]}]=true; app_args[riplib]=true
      else cliriplib[${app_args[cli]}]=false; app_args[riplib]=false; fi
    fi
    if [ "${app_args[riplib]}" = true ] && [ "$(toml_get "$t" riplib || printf '')" = "false" ]; then app_args[riplib]=false; fi
    app_args[rv_brand]=$(toml_get "$t" rv-brand || printf '%s' "$DEF_RV_BRAND")
    app_args[excluded_patches]=$(toml_get "$t" excluded-patches || printf '')
    [ -n "${app_args[excluded_patches]}" ] && [[ ${app_args[excluded_patches]} != *'"'* ]] && abort "patch names inside excluded-patches must be quoted"
    app_args[included_patches]=$(toml_get "$t" included-patches || printf '')
    [ -n "${app_args[included_patches]}" ] && [[ ${app_args[included_patches]} != *'"'* ]] && abort "patch names inside included-patches must be quoted"
    app_args[exclusive_patches]=$(toml_get "$t" exclusive-patches || printf 'false'); vtf "${app_args[exclusive_patches]}" "exclusive-patches"
    app_args[version]=$(toml_get "$t" version || printf 'auto')
    app_args[app_name]=$(toml_get "$t" app-name || printf '%s' "$table_name")
    app_args[patcher_args]=$(toml_get "$t" patcher-args || printf '')
    app_args[table]=$table_name
    app_args[uptodown_dlurl]=$(toml_get "$t" uptodown-dlurl || printf '')
    [ -n "${app_args[uptodown_dlurl]}" ] && { app_args[uptodown_dlurl]=${app_args[uptodown_dlurl]%/}; app_args[uptodown_dlurl]=${app_args[uptodown_dlurl]%download}; app_args[uptodown_dlurl]=${app_args[uptodown_dlurl]%/}; app_args[dl_from]=uptodown; }
    app_args[apkmirror_dlurl]=$(toml_get "$t" apkmirror-dlurl || printf '')
    [ -n "${app_args[apkmirror_dlurl]}" ] && { app_args[apkmirror_dlurl]=${app_args[apkmirror_dlurl]%/}; app_args[dl_from]=apkmirror; }
    app_args[archive_dlurl]=$(toml_get "$t" archive-dlurl || printf '')
    [ -n "${app_args[archive_dlurl]}" ] && { app_args[archive_dlurl]=${app_args[archive_dlurl]%/}; app_args[dl_from]=archive; }
    [ -z "${app_args[dl_from]-}" ] && abort "ERROR: no 'apkmirror_dlurl', 'uptodown_dlurl' or 'archive_dlurl' set for '$table_name'."
    app_args[arch]=$(toml_get "$t" arch || printf 'all')
    if [ "${app_args[arch]}" != "both" ] && [ "${app_args[arch]}" != "all" ] && [[ ${app_args[arch]} != "arm64-v8a"* ]] && [[ ${app_args[arch]} != "arm-v7a"* ]]; then abort "wrong arch '${app_args[arch]}' for '$table_name'"; fi
    app_args[dpi]=$(toml_get "$t" dpi || printf 'nodpi')
    if [ "${app_args[arch]}" = both ]; then
      app_args[table]="$table_name (arm64-v8a)"; app_args[arch]="arm64-v8a"; idx=$((idx+1)); build_rv "$(declare -p app_args)" &
      app_args[table]="$table_name (arm-v7a)"; app_args[arch]="arm-v7a"; ((idx >= PARALLEL_JOBS)) && { wait -n; idx=$((idx-1)); }; idx=$((idx+1)); build_rv "$(declare -p app_args)" &
    else
      idx=$((idx+1)); build_rv "$(declare -p app_args)" &
    fi
  done
  wait
  rm -rf "$TEMP_DIR"/tmp.*
  if [ -z "$(ls -A1 "${BUILD_DIR}")" ]; then abort "All builds failed."; fi
  if [ "$OS" = "Android" ]; then
    pr "Moving outputs to /sdcard/Download/rvx-output"
    for apk in "${BUILD_DIR}"/*; do [ -f "$apk" ] && { mv -f "$apk" "$OUTPUT_DIR/"; pr "$(basename "$apk")"; }; done
    am start -a android.intent.action.VIEW -d "file:///sdcard/Download/rvx-output" -t resource/folder >/dev/null 2>&1 || :
  fi
  log "\n- ▶️ » Install [MicroG-RE](https://github.com/WSTxda/MicroG-RE/releases) for YouTube and YT Music APKs\n"
  log "$(cat "$TEMP_DIR"/*-rv/changelog.md 2>/dev/null || true)"
  SKIPPED=$(cat "$TEMP_DIR"/skipped 2>/dev/null || true)
  [ -n "$SKIPPED" ] && { log "\nSkipped:"; log "$SKIPPED"; }
  pr "Done"
}

main "$@"
