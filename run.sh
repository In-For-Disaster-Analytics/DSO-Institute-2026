#!/bin/bash
set -xe

# Repository Variables
# GIT_REPO_URL: URL of the repository to clone where the notebook and environment files are located
# COOKBOOK_NAME: Name of the cookbook
# COOKBOOK_CONDA_ENV: Name of the conda environment
# IS_GPU_JOB: Boolean value to indicate if the job is a GPU job. If true, it will load the CUDA module
export GIT_REPO_URL="https://github.com/In-For-Disaster-Analytics/DSO-Institute-2026.git"
export COOKBOOK_NAME="DSO-Summer-Institute-2026"
export COOKBOOK_CONDA_ENV="DSO-Institute"
export COOKBOOK_KERNEL_DISPLAY_NAME="Python (DSO-Institute)"
export CKAN_JUPYTER_REPO_URL="https://github.com/In-For-Disaster-Analytics/ckan-jupyter.git"
export CKAN_JUPYTER_MARKER_VERSION="repo:${CKAN_JUPYTER_REPO_URL}"
export USE_CONDA_PACK_TARBALLS="true"
export ENV_PACK_SEARCH_DIRS="/work/06659/wmobley"
IS_GPU_JOB=false


# Cookbook Variables
# PARAM 1 is kept for app compatibility. Repository updates now run on every startup.
# UPDATE_CONDA_ENV: Boolean value to update the conda environment
# GIT_BRANCH: Branch of the repository to clone
if [ "$#" -ne 3 ]; then
	echo "Illegal number of parameters"
	exit 1
fi
if [ "$2" != "true" ] && [ "$2" != "false" ]; then
	echo "The second parameter must be a boolean value to update the conda environment"
	exit 1
fi

export DOWNLOAD_LATEST_VERSION="true"
export UPDATE_CONDA_ENV=$2
export GIT_BRANCH=$3

function init_job_condarc() {
    # Use an isolated CONDARC so user-level ~/.condarc alias conflicts
    # (e.g., auto_activate + auto_activate_base) cannot break this job.
    export CONDARC="${WORK}/.condarc-${SLURM_JOB_ID:-$$}.yaml"
    cat > "${CONDARC}" <<'EOF'
auto_activate: false
channel_priority: strict
solver: libmamba
channels:
  - conda-forge
  - defaults
EOF
    echo "Using isolated CONDARC at ${CONDARC}"
}

function install_conda() {
	CONDA_ROOT="$WORK/miniconda3"
	CONDA_BIN="$CONDA_ROOT/bin/conda"
	CONDA_INSTALLER="$CONDA_ROOT/miniconda.sh"

	echo "Checking if miniconda3 is installed..."
	if [ ! -x "$CONDA_BIN" ]; then
		echo "Miniconda missing or incomplete in $CONDA_ROOT..."
		echo "Installing..."
		rm -rf "$CONDA_ROOT"
		mkdir -p "$CONDA_ROOT"
		curl https://repo.anaconda.com/miniconda/Miniconda3-py311_23.10.0-1-Linux-x86_64.sh -o "$CONDA_INSTALLER"
		bash "$CONDA_INSTALLER" -b -u -p "$CONDA_ROOT"
		rm -f "$CONDA_INSTALLER"
	fi

	export PATH="$CONDA_ROOT/bin:$PATH"
	if ! command -v conda >/dev/null 2>&1; then
		echo "ERROR: conda command is not available after installation/setup"
		exit 1
	fi

	echo "Ensuring conda base environment is OFF..."
	"$CONDA_BIN" config --set auto_activate_base false

	# Initialize conda for this non-interactive shell without depending on ~/.bashrc edits.
	if [ -f "$CONDA_ROOT/etc/profile.d/conda.sh" ]; then
		# shellcheck source=/dev/null
		source "$CONDA_ROOT/etc/profile.d/conda.sh"
	else
		eval "$("$CONDA_BIN" shell.bash hook)"
	fi
	unset PYTHONPATH
}

function load_cuda() {
	echo "Loading CUDA..."
	module load cuda/12.0
}

function export_repo_variables() {
	COOKBOOK_DIR=${WORK}/cookbooks
	COOKBOOK_WORKSPACE_DIR=${COOKBOOK_DIR}/${COOKBOOK_NAME}
	COOKBOOK_REPOSITORY_PARENT_DIR=${COOKBOOK_DIR}/.repository
	COOKBOOK_REPOSITORY_DIR=${COOKBOOK_REPOSITORY_PARENT_DIR}/${COOKBOOK_NAME}
	UPDATE_AVAILABLE_FILE=${COOKBOOK_WORKSPACE_DIR}/UPDATE_AVAILABLE.txt
	WORKSPACE_SYNC_STATE_FILE=${COOKBOOK_WORKSPACE_DIR}/.cookbook-sync-commit
	NODE_HOSTNAME_PREFIX=$(hostname -s) # Short Host Name  -->  name of compute node: c###-###
	NODE_HOSTNAME_DOMAIN=$(hostname -d) # DNS Name  -->  stampede2.tacc.utexas.edu
	NODE_HOSTNAME_LONG=$(hostname -f)   # Fully Qualified Domain Name  -->  c###-###.stampede2.tacc.utexas.edu
	export COOKBOOK_DIR
	export COOKBOOK_WORKSPACE_DIR
	export COOKBOOK_REPOSITORY_DIR
	export COOKBOOK_REPOSITORY_PARENT_DIR
	export UPDATE_AVAILABLE_FILE
	export WORKSPACE_SYNC_STATE_FILE
	export NODE_HOSTNAME_PREFIX
	export NODE_HOSTNAME_DOMAIN
	export NODE_HOSTNAME_LONG
}

function init_timing_log() {
	TIMING_LOG_FILE="${COOKBOOK_WORKSPACE_DIR}/setup_timing_${SLURM_JOB_ID:-$$}.log"
	export TIMING_LOG_FILE
	{
		echo "# DSO setup timing log"
		echo "# started_at_utc $(date -u +%Y-%m-%dT%H:%M:%SZ)"
	} >"${TIMING_LOG_FILE}"
}

function timed_step() {
	local step_name="$1"
	shift

	local start_epoch
	local end_epoch
	local duration_seconds
	local step_status
	local start_utc
	local end_utc

	start_epoch=$(date +%s)
	start_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
	echo "TACC: START ${step_name} at ${start_utc}"

	set +e
	"$@"
	step_status=$?
	set -e

	end_epoch=$(date +%s)
	end_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
	duration_seconds=$((end_epoch - start_epoch))

	echo "TACC: END ${step_name} status=${step_status} duration=${duration_seconds}s at ${end_utc}"
	if [ -n "${TIMING_LOG_FILE:-}" ]; then
		printf "%s\t%s\tstatus=%s\tduration=%ss\n" "${end_utc}" "${step_name}" "${step_status}" "${duration_seconds}" >>"${TIMING_LOG_FILE}"
	fi

	return "${step_status}"
}

function resolve_env_pack_tarball() {
	local env_name="$1"
	local search_dirs="${ENV_PACK_SEARCH_DIRS}"
	local search_dir
	local exact_tarball
	local dated_tarball
	local parsed_dirs=()

	IFS=':' read -r -a parsed_dirs <<< "${search_dirs}"
	for search_dir in "${parsed_dirs[@]}"; do
		[ -z "${search_dir}" ] && continue
		exact_tarball="${search_dir}/${env_name}.tar.gz"
		if [ -f "${exact_tarball}" ]; then
			echo "${exact_tarball}"
			return 0
		fi

		dated_tarball=$(ls -1t "${search_dir}/${env_name}"-*.tar.gz 2>/dev/null | head -n 1)
		if [ -n "${dated_tarball}" ]; then
			echo "${dated_tarball}"
			return 0
		fi
	done

	return 1
}

function restore_conda_environment_from_pack() {
	local env_name="$1"
	local env_prefix="$WORK/miniconda3/envs/${env_name}"
	local tarball_path
	local unpack_status

	if [ "${USE_CONDA_PACK_TARBALLS}" != "true" ]; then
		echo "TACC: TARBALL_RESTORE_DISABLED env=${env_name}"
		return 1
	fi

	if ! tarball_path=$(resolve_env_pack_tarball "${env_name}"); then
		echo "TACC: TARBALL_RESTORE_MISSING env=${env_name} search_dirs=${ENV_PACK_SEARCH_DIRS}"
		return 1
	fi

	if [ -d "${env_prefix}" ] && [ "${UPDATE_CONDA_ENV}" != "true" ]; then
		echo "TACC: TARBALL_RESTORE_REUSE env=${env_name} prefix=${env_prefix}"
		return 0
	fi

	echo "TACC: TARBALL_RESTORE_START env=${env_name} tarball=${tarball_path} prefix=${env_prefix}"
	rm -rf "${env_prefix}"
	mkdir -p "${env_prefix}"
	if ! tar -xzf "${tarball_path}" -C "${env_prefix}"; then
		echo "TACC: TARBALL_RESTORE_EXTRACT_FAILED env=${env_name} tarball=${tarball_path}"
		rm -rf "${env_prefix}"
		return 1
	fi

	if [ ! -x "${env_prefix}/bin/conda-unpack" ]; then
		echo "TACC: TARBALL_RESTORE_MISSING_UNPACK env=${env_name} prefix=${env_prefix}"
		rm -rf "${env_prefix}"
		return 1
	fi

	set +e
	"${env_prefix}/bin/conda-unpack"
	unpack_status=$?
	set -e
	if [ "${unpack_status}" -ne 0 ]; then
		echo "TACC: TARBALL_RESTORE_UNPACK_FAILED env=${env_name} prefix=${env_prefix} status=${unpack_status}"
		rm -rf "${env_prefix}"
		return 1
	fi
	echo "TACC: TARBALL_RESTORE_DONE env=${env_name} prefix=${env_prefix}"
	return 0
}

function update_cookbook_repository() {
	COOKBOOK_REPOSITORY_PREVIOUS_HEAD=""
	COOKBOOK_REPOSITORY_CURRENT_HEAD=""

	if [ ! -d "${COOKBOOK_REPOSITORY_DIR}/.git" ]; then
		rm -rf "${COOKBOOK_REPOSITORY_DIR}"
		git clone "${GIT_REPO_URL}" --branch "${GIT_BRANCH}" "${COOKBOOK_REPOSITORY_DIR}"
		COOKBOOK_REPOSITORY_CURRENT_HEAD=$(git -C "${COOKBOOK_REPOSITORY_DIR}" rev-parse HEAD)
		return 0
	fi

	git -C "${COOKBOOK_REPOSITORY_DIR}" checkout "${GIT_BRANCH}"
	COOKBOOK_REPOSITORY_PREVIOUS_HEAD=$(git -C "${COOKBOOK_REPOSITORY_DIR}" rev-parse HEAD)

	if [ "${DOWNLOAD_LATEST_VERSION}" = "true" ]; then
		git -C "${COOKBOOK_REPOSITORY_DIR}" fetch origin "${GIT_BRANCH}"
		git -C "${COOKBOOK_REPOSITORY_DIR}" checkout "${GIT_BRANCH}"
		git -C "${COOKBOOK_REPOSITORY_DIR}" reset --hard "origin/${GIT_BRANCH}"
	fi

	COOKBOOK_REPOSITORY_CURRENT_HEAD=$(git -C "${COOKBOOK_REPOSITORY_DIR}" rev-parse HEAD)
}

function read_workspace_sync_commit() {
	if [ -f "${WORKSPACE_SYNC_STATE_FILE}" ]; then
		cat "${WORKSPACE_SYNC_STATE_FILE}"
	fi
}

function infer_workspace_sync_commit() {
	local candidate_ref=""
	local candidate_commit=""

	if [ -d "${COOKBOOK_WORKSPACE_DIR}/.git" ]; then
		for candidate_ref in "origin/${GIT_BRANCH}" "HEAD"; do
			if candidate_commit=$(git -C "${COOKBOOK_WORKSPACE_DIR}" rev-parse --verify "${candidate_ref}" 2>/dev/null); then
				if git -C "${COOKBOOK_REPOSITORY_DIR}" cat-file -e "${candidate_commit}^{commit}" 2>/dev/null; then
					echo "${candidate_commit}"
					return 0
				fi
			fi
		done
	fi

	if [ -n "${COOKBOOK_REPOSITORY_PREVIOUS_HEAD}" ]; then
		echo "${COOKBOOK_REPOSITORY_PREVIOUS_HEAD}"
		return 0
	fi

	return 1
}

function write_workspace_sync_commit() {
	printf "%s\n" "${COOKBOOK_REPOSITORY_CURRENT_HEAD}" > "${WORKSPACE_SYNC_STATE_FILE}"
}

function copy_repo_file_to_workspace() {
	local relative_path="$1"
	local source_path="${COOKBOOK_REPOSITORY_DIR}/${relative_path}"
	local target_path="${COOKBOOK_WORKSPACE_DIR}/${relative_path}"

	mkdir -p "$(dirname "${target_path}")"
	cp -p "${source_path}" "${target_path}"
}

function workspace_file_matches_repo_commit() {
	local relative_path="$1"
	local commit_ref="$2"
	local workspace_path="${COOKBOOK_WORKSPACE_DIR}/${relative_path}"

	if [ ! -f "${workspace_path}" ]; then
		return 1
	fi

	if ! git -C "${COOKBOOK_REPOSITORY_DIR}" cat-file -e "${commit_ref}:${relative_path}" 2>/dev/null; then
		return 1
	fi

	if git -C "${COOKBOOK_REPOSITORY_DIR}" show "${commit_ref}:${relative_path}" | cmp -s - "${workspace_path}"; then
		return 0
	fi

	return 1
}

function record_workspace_update_notice() {
	local message="$1"
	local relative_path="$2"

	if [ ! -f "${UPDATE_AVAILABLE_FILE}" ]; then
		cat <<'EOF' > "${UPDATE_AVAILABLE_FILE}"
Repository updates were skipped for the files below because the local copy was changed.
Review these files and merge any needed updates manually.

EOF
	fi

	printf "%s: %s\n" "${message}" "${relative_path}" >> "${UPDATE_AVAILABLE_FILE}"
}

function sync_cookbook_workspace() {
	mkdir -p "${COOKBOOK_WORKSPACE_DIR}"
	rsync -a --exclude '.git' "${COOKBOOK_REPOSITORY_DIR}/" "${COOKBOOK_WORKSPACE_DIR}/"
	write_workspace_sync_commit
	rm -f "${UPDATE_AVAILABLE_FILE}"
	echo "TACC: WORKSPACE_SYNC mode=full commit=${COOKBOOK_REPOSITORY_CURRENT_HEAD}"
}

function initialize_workspace_sync_state() {
	local inferred_commit=""

	if [ -f "${WORKSPACE_SYNC_STATE_FILE}" ]; then
		return 0
	fi

	if inferred_commit=$(infer_workspace_sync_commit); then
		printf "%s\n" "${inferred_commit}" > "${WORKSPACE_SYNC_STATE_FILE}"
		echo "TACC: WORKSPACE_SYNC_STATE initialized_from=${inferred_commit}"
		return 0
	fi

	write_workspace_sync_commit
	echo "TACC: WORKSPACE_SYNC_STATE initialized_from=current_head_without_known_base commit=${COOKBOOK_REPOSITORY_CURRENT_HEAD}"
}

function sync_cookbook_workspace_updates() {
	local base_commit="$1"
	local relative_path=""
	local workspace_path=""
	local added_count=0
	local updated_count=0
	local preserved_count=0
	local deleted_count=0
	local skipped_count=0

	if [ -z "${base_commit}" ]; then
		return 0
	fi

	rm -f "${UPDATE_AVAILABLE_FILE}"
	echo "TACC: WORKSPACE_SYNC mode=incremental base_commit=${base_commit} target_commit=${COOKBOOK_REPOSITORY_CURRENT_HEAD}"

	# Only replace files that still match the last synced commit.
	while IFS= read -r -d '' relative_path; do
		workspace_path="${COOKBOOK_WORKSPACE_DIR}/${relative_path}"

		if [ ! -e "${workspace_path}" ]; then
			copy_repo_file_to_workspace "${relative_path}"
			added_count=$((added_count + 1))
			continue
		fi

		if git -C "${COOKBOOK_REPOSITORY_DIR}" cat-file -e "${base_commit}:${relative_path}" 2>/dev/null; then
			if workspace_file_matches_repo_commit "${relative_path}" "${base_commit}"; then
				copy_repo_file_to_workspace "${relative_path}"
				updated_count=$((updated_count + 1))
			else
				record_workspace_update_notice "Preserved local changes" "${relative_path}"
				preserved_count=$((preserved_count + 1))
			fi
		else
			record_workspace_update_notice "Skipped new upstream file because a local file already exists" "${relative_path}"
			skipped_count=$((skipped_count + 1))
		fi
	done < <(git -C "${COOKBOOK_REPOSITORY_DIR}" diff --name-only -z --diff-filter=ACMRT "${base_commit}" HEAD)

	while IFS= read -r -d '' relative_path; do
		workspace_path="${COOKBOOK_WORKSPACE_DIR}/${relative_path}"

		if [ ! -e "${workspace_path}" ]; then
			continue
		fi

		if workspace_file_matches_repo_commit "${relative_path}" "${base_commit}"; then
			rm -f "${workspace_path}"
			deleted_count=$((deleted_count + 1))
		else
			record_workspace_update_notice "Kept local file that was deleted upstream" "${relative_path}"
			preserved_count=$((preserved_count + 1))
		fi
	done < <(git -C "${COOKBOOK_REPOSITORY_DIR}" diff --name-only -z --diff-filter=D "${base_commit}" HEAD)

	write_workspace_sync_commit
	echo "TACC: WORKSPACE_SYNC_RESULT added=${added_count} updated=${updated_count} deleted=${deleted_count} preserved=${preserved_count} skipped=${skipped_count}"
}

function init_directory() {
	mkdir -p ${COOKBOOK_REPOSITORY_PARENT_DIR}
	update_cookbook_repository

	if [ ! -d "${COOKBOOK_WORKSPACE_DIR}" ]; then
		sync_cookbook_workspace
		return 0
	fi

	initialize_workspace_sync_state

	if [ "${DOWNLOAD_LATEST_VERSION}" = "true" ]; then
		sync_cookbook_workspace_updates "$(read_workspace_sync_commit)"
	fi
}

function get_tap_certificate() {
	mkdir -p ${HOME}/.tap # this should exist at this point, but just in case...
	export TAP_CERTFILE=${HOME}/.tap/.${SLURM_JOB_ID}
	# bail if we cannot create a secure session
	if [ ! -f ${TAP_CERTFILE} ]; then
		echo "TACC: ERROR - could not find TLS cert for secure session"
		echo "TACC: job ${SLURM_JOB_ID} execution finished at: $(date)"
		exit 1
	fi
}

function get_tap_token() {
	# bail if we cannot create a token for the session
	TAP_TOKEN=$(tap_get_token)
	if [ -z "${TAP_TOKEN}" ]; then
		echo "TACC: ERROR - could not generate token for jupyter session"
		echo "TACC: job ${SLURM_JOB_ID} execution finished at: $(date)"
		exit 1
	fi
	echo "TACC: using token ${TAP_TOKEN}"
	LOGIN_PORT=$(tap_get_port)
	export TAP_TOKEN
	export LOGIN_PORT
}

function load_tap_functions() {
	TAP_FUNCTIONS="/share/doc/slurm/tap_functions"
	if [ -f ${TAP_FUNCTIONS} ]; then
		. ${TAP_FUNCTIONS}
	else
		echo "TACC:"
		echo "TACC: ERROR - could not find TAP functions file: ${TAP_FUNCTIONS}"
		echo "TACC: ERROR - Please submit a consulting ticket at the TACC user portal"
		echo "TACC: ERROR - https://portal.tacc.utexas.edu/tacc-consulting/-/consult/tickets/create"
		echo "TACC:"
		echo "TACC: job $SLURM_JOB_ID execution finished at: $(date)"
		exit 1
	fi
}

function create_jupyter_configuration {
	mkdir -p ${HOME}/.tap
	TAP_JUPYTER_CONFIG="${HOME}/.tap/jupyter_config.py"
	JUPYTER_SERVER_APP="ServerApp"
	JUPYTER_BIN="jupyter-lab"
	LOCAL_PORT=5902
	echo ${PWD}

	cat <<-EOF >${TAP_JUPYTER_CONFIG}
		# Configuration file for TAP jupyter session
		import ssl
		c = get_config()
		c.IPKernelApp.pylab = "inline"  # if you want plotting support always
		c.${JUPYTER_SERVER_APP}.ip = "0.0.0.0"
		c.${JUPYTER_SERVER_APP}.port = $LOCAL_PORT
		c.${JUPYTER_SERVER_APP}.open_browser = False
		c.${JUPYTER_SERVER_APP}.allow_origin = u"*"
		c.${JUPYTER_SERVER_APP}.ssl_options = {"ssl_version": ssl.PROTOCOL_TLSv1_2}
		c.${JUPYTER_SERVER_APP}.root_dir = "${_tapisJobWorkingDir}"
		c.${JUPYTER_SERVER_APP}.preferred_dir = "${_tapisJobWorkingDir}"
		c.${JUPYTER_SERVER_APP}.notebook_dir = "${_tapisJobWorkingDir}/work"
		c.FileContentsManager.delete_to_trash = False
		c.IdentityProvider.token = "${TAP_TOKEN}"
		c.MultiKernelManager.default_kernel_name = "${COOKBOOK_CONDA_ENV}"
	EOF

}

function run_jupyter() {
	conda activate ${COOKBOOK_CONDA_ENV}
	export NLTK_DATA="${HOME}/nltk_data"
	NB_SERVERDIR=$HOME/.jupyter
	JUPYTER_SERVER_APP="ServerApp"
	JUPYTER_BIN="jupyter-lab"
	JUPYTER_ARGS="--certfile=$(cat ${TAP_CERTFILE}) --config=${TAP_JUPYTER_CONFIG}"
	JUPYTER_LOGFILE=${NB_SERVERDIR}/${NODE_HOSTNAME_PREFIX}.log
	mkdir -p ${NB_SERVERDIR}
	touch $JUPYTER_LOGFILE
	nohup ${JUPYTER_BIN} ${JUPYTER_ARGS} &>${JUPYTER_LOGFILE} &
	JUPYTER_PID=$!
	sleep 5
	# verify jupyter is listening. if not, give it one more try, then bail
	if ! python - <<PY
import socket
sock = socket.socket()
sock.settimeout(1)
try:
    sock.connect(("127.0.0.1", 5902))
except OSError:
    raise SystemExit(1)
finally:
    sock.close()
PY
	then
		# sometimes jupyter has a bad day. give it another chance to be awesome.
		echo "TACC: first jupyter launch failed. Retrying..."
		nohup ${JUPYTER_BIN} ${JUPYTER_ARGS} &>${JUPYTER_LOGFILE} &
		sleep 5
	fi

	if ! python - <<PY
import socket
sock = socket.socket()
sock.settimeout(1)
try:
    sock.connect(("127.0.0.1", 5902))
except OSError:
    raise SystemExit(1)
finally:
    sock.close()
PY
	then
		# jupyter will not be working today. sadness.
		echo "TACC: ERROR - jupyter failed to launch"
		echo "TACC: ERROR - this is often due to an issue in your python or conda environment, or Jupyter failing to bind its port"
		echo "TACC: ERROR - jupyter logfile contents:"
		cat ${JUPYTER_LOGFILE}
		echo "TACC: job ${SLURM_JOB_ID} execution finished at: $(date)"
		exit 1
	fi

}

function port_fowarding() {
	LOCAL_PORT=5902
	LOGIN_NODE_COUNT=3
	TUNNEL_LOGFILE="${HOME}/.jupyter/${NODE_HOSTNAME_PREFIX}-ssh-tunnels.log"
	local ssh_status=0
	local login_node=""
	local successful_login_node=""
	# Disable exit on error so we can check the ssh tunnel status.
	set +e
	: > "${TUNNEL_LOGFILE}"
	for i in $(seq ${LOGIN_NODE_COUNT}); do
		login_node="login${i}"
		echo "TACC: opening reverse tunnel on ${login_node}" | tee -a "${TUNNEL_LOGFILE}"
		ssh -o StrictHostKeyChecking=no -f -g -N -R ${LOGIN_PORT}:${NODE_HOSTNAME_PREFIX}:${LOCAL_PORT} "${login_node}" >>"${TUNNEL_LOGFILE}" 2>&1
		ssh_status=$?
		if [ "${ssh_status}" -ne 0 ]; then
			echo "TACC: ERROR - reverse tunnel setup failed on ${login_node} with exit code ${ssh_status}" | tee -a "${TUNNEL_LOGFILE}"
			continue
		fi

		if [ -z "${successful_login_node}" ]; then
			successful_login_node="${login_node}"
		fi
	done
	set -e

	if [ -z "${successful_login_node}" ]; then
		# jupyter will not be working today. sadness.
		echo "TACC: ERROR - ssh tunnels failed to launch"
		echo "TACC: ERROR - this is often due to an issue with your ssh keys"
		echo "TACC: ERROR - ssh tunnel logfile contents:"
		cat "${TUNNEL_LOGFILE}"
		echo "TACC: ERROR - undo any recent mods in ${HOME}/.ssh"
		echo "TACC: ERROR - or submit a TACC consulting ticket with this error"
		echo "TACC: job ${SLURM_JOB_ID} execution finished at: $(date)"
		exit 1
	fi

	JUPYTER_PUBLIC_HOST="${successful_login_node}.${NODE_HOSTNAME_DOMAIN}"
	export JUPYTER_PUBLIC_HOST
	echo "TACC: using public login host ${JUPYTER_PUBLIC_HOST}" | tee -a "${TUNNEL_LOGFILE}"
}

function send_url_to_webhook() {
	JUPYTER_PUBLIC_HOST="${JUPYTER_PUBLIC_HOST:-${NODE_HOSTNAME_DOMAIN}}"
	JUPYTER_URL="https://${JUPYTER_PUBLIC_HOST}:${LOGIN_PORT}/?token=${TAP_TOKEN}"
	INTERACTIVE_WEBHOOK_URL="${_webhook_base_url:-${_INTERACTIVE_WEBHOOK_URL:-}}"
	echo "TACC:     JUPYTER_URL is ${JUPYTER_URL}"
	if [ -z "${INTERACTIVE_WEBHOOK_URL}" ]; then
		echo "TACC: WARNING - interactive webhook URL is not set; skipping callback"
		echo "TACC: WARNING - open the Jupyter URL above directly if the portal does not redirect automatically"
		return 0
	fi
	# Wait a few seconds for jupyter to boot up and send webhook callback url for job ready notification.
	# Notification is sent to _INTERACTIVE_WEBHOOK_URL, e.g. https://3dem.org/webhooks/interactive/
	(
		sleep 5 &&
			curl -k --data "event_type=interactive_session_ready&address=${JUPYTER_URL}&owner=${_tapisJobOwner}&job_uuid=${_tapisJobUUID}" "${INTERACTIVE_WEBHOOK_URL}" &
	) &

}

function session_cleanup() {
	# This file will be located in the directory mounted by the job.
	SESSION_FILE=delete_me_to_end_session
	touch $SESSION_FILE
	echo $NODE_HOSTNAME_LONG $IPYTHON_PID >$SESSION_FILE
	# While the session file remains undeleted, keep Jupyter session running.
	while [ -f $SESSION_FILE ]; do
		sleep 10
	done
}

function conda_environment_exists() {
	local env_name="$1"
	local env_prefix="${WORK}/miniconda3/envs/${env_name}"

	[ -d "${env_prefix}" ]
}

function configure_nltk_data() {
	export NLTK_DATA="${HOME}/nltk_data"
	mkdir -p "${NLTK_DATA}"

	conda run -n "${COOKBOOK_CONDA_ENV}" python - <<'PY'
import os
import nltk

nltk_data_dir = os.environ["NLTK_DATA"]
packages = [
    "punkt",
    "punkt_tab",
    "stopwords",
    "averaged_perceptron_tagger",
]

for package in packages:
    nltk.download(package, download_dir=nltk_data_dir, quiet=True)
PY
}

function install_ckan_jupyter_extension() {
	local marker_version="${CKAN_JUPYTER_MARKER_VERSION}"
	local ckan_marker_script

	ckan_marker_script="$(mktemp)"
	cat <<'PY' >"${ckan_marker_script}"
from pathlib import Path
import os
import sys
import site

expected = os.environ["CKAN_JUPYTER_MARKER_VERSION"]
env_prefix = Path(sys.prefix)
site_packages = [Path(path) for path in site.getsitepackages()]
candidate_roots = site_packages + [env_prefix]
marker_path = env_prefix / "share" / "jupyter" / "labextensions" / "@dso" / "ckan-jupyter" / ".install-marker"

try:
    import ckan_jupyter  # noqa: F401
except Exception:
    print("ckan_jupyter import check failed; installation is required")
    raise SystemExit(3)

lab_source = None
for root in candidate_roots:
    candidate = root / "ckan_jupyter" / "labextension"
    if candidate.is_dir() and (candidate / "package.json").is_file():
        lab_source = candidate
        break

if lab_source is None:
    print("ckan_jupyter labextension source is missing; installation is required")
    raise SystemExit(4)

if marker_path.is_file() and marker_path.read_text().strip() == expected:
    print(f"ckan-jupyter marker matches ({expected}); skipping reinstall")
    raise SystemExit(0)

print("ckan-jupyter marker missing or changed; installation is required")
raise SystemExit(5)
PY

	if conda run -n "${COOKBOOK_CONDA_ENV}" env CKAN_JUPYTER_MARKER_VERSION="${marker_version}" python "${ckan_marker_script}"; then
		rm -f "${ckan_marker_script}"
		return 0
	fi
	rm -f "${ckan_marker_script}"

	conda run -n "${COOKBOOK_CONDA_ENV}" python -m pip install --no-cache-dir --no-build-isolation "git+${CKAN_JUPYTER_REPO_URL}"
	conda run -n "${COOKBOOK_CONDA_ENV}" python -m jupyter server extension enable --sys-prefix --py ckan_jupyter
	CKAN_JUPYTER_COPY_SCRIPT="$(mktemp)"
cat <<'PY' > "${CKAN_JUPYTER_COPY_SCRIPT}"
from pathlib import Path
import os
import shutil
import site
import sys

env_prefix = Path(sys.prefix)
site_packages = [Path(path) for path in site.getsitepackages()]
candidate_roots = site_packages + [env_prefix]

lab_source = None
for root in candidate_roots:
    candidate = root / "ckan_jupyter" / "labextension"
    if candidate.is_dir() and (candidate / "package.json").is_file():
        lab_source = candidate
        break

if lab_source is None:
    raise SystemExit("TACC: ERROR - ckan-jupyter labextension bundle was not found after install")

lab_dest = env_prefix / "share" / "jupyter" / "labextensions" / "@dso" / "ckan-jupyter"
lab_dest.parent.mkdir(parents=True, exist_ok=True)

if lab_dest.exists():
    shutil.rmtree(lab_dest)

shutil.copytree(lab_source, lab_dest)
marker_path = lab_dest / ".install-marker"
marker_path.write_text(os.environ["CKAN_JUPYTER_MARKER_VERSION"] + "\n")
print(f"Installed ckan-jupyter labextension to {lab_dest}")
PY
	conda run -n "${COOKBOOK_CONDA_ENV}" env CKAN_JUPYTER_MARKER_VERSION="${marker_version}" python "${CKAN_JUPYTER_COPY_SCRIPT}"
	rm -f "${CKAN_JUPYTER_COPY_SCRIPT}"
}

function install_spacy_model() {
	conda run -n "${COOKBOOK_CONDA_ENV}" python -m spacy download en_core_web_sm
}
function download_opera_setup_env() {
	wget -P "${COOKBOOK_WORKSPACE_DIR}/Day-4/setup_env.py" \
	"https://raw.githubusercontent.com/OPERA-Cal-Val/OPERA_Applications/main/DISP/Discover/setup_env.py"

	echo "setup_env.py downloaded successfully"
}
function patch_disp_xr_python_constraint() {
    TOOLS_DIR="$1"
    PYPROJECT="${TOOLS_DIR}/disp-xr/pyproject.toml"

    if [ -f "${PYPROJECT}" ]; then
        python - <<PY
from pathlib import Path

path = Path("${PYPROJECT}")
text = path.read_text()
lines = []

for line in text.splitlines():
    if line.strip().startswith("requires-python"):
        lines.append('requires-python = ">=3.11.13"')
    else:
        lines.append(line)

path.write_text("\\n".join(lines) + "\\n")
print(f"Patched Python constraint in {path}")
PY
    else
        echo "WARNING: disp-xr pyproject.toml not found at ${PYPROJECT}"
    fi
}
function install_displacement_tools() {
    ENV_NAME="$1"
    TOOLS_DIR="${COOKBOOK_WORKSPACE_DIR}/Day-4/displacement_tools"

    mkdir -p "${TOOLS_DIR}"

    if [ ! -d "${TOOLS_DIR}/MintPy" ]; then
        git clone https://github.com/insarlab/MintPy.git "${TOOLS_DIR}/MintPy"
    fi

    if [ ! -d "${TOOLS_DIR}/disp-xr" ]; then
        git clone https://github.com/opera-adt/disp-xr.git "${TOOLS_DIR}/disp-xr"
    fi

    patch_disp_xr_python_constraint "${TOOLS_DIR}"

    conda run -n "${ENV_NAME}" python -m pip install --no-cache-dir -e "${TOOLS_DIR}/MintPy"
    conda run -n "${ENV_NAME}" python -m pip install --no-cache-dir -e "${TOOLS_DIR}/disp-xr"

    conda run -n "${ENV_NAME}" python -m pip install --no-cache-dir \
        rasterio \
        rioxarray \
        asf_search \
        opera_utils \
        numcodecs \
        s3fs \
        dem_stitcher \
        tile_mate \
        contextily \
        folium \
        zarr \
        h5netcdf \
        h5py
}

function create_conda_environment() {
	ENV_FILENAME="$1"
	ENV_NAME="$2"
	ENV_FILE="${COOKBOOK_WORKSPACE_DIR}/.binder/${ENV_FILENAME}"
	local restored_from_tarball="false"

	if [ -z "${ENV_FILENAME}" ]; then
		echo "TACC: ERROR - No environment file name provided"
		exit 1
	fi

	if [ -z "${ENV_NAME}" ]; then
		echo "TACC: ERROR - No conda environment name provided"
		exit 1
	fi

	if [ "${USE_CONDA_PACK_TARBALLS}" = "true" ]; then
		echo "TACC: CREATE_ENV_MODE env=${ENV_NAME} mode=tarball_only"
		if timed_step "restore_conda_pack:${ENV_NAME}" restore_conda_environment_from_pack "${ENV_NAME}"; then
			echo "TACC: CREATE_ENV_READY env=${ENV_NAME} source=tarball"
			restored_from_tarball="true"
		else
			echo "TACC: CREATE_ENV_FAILED env=${ENV_NAME} source=tarball"
			return 1
		fi
	fi

	if [ "${restored_from_tarball}" != "true" ]; then
		echo "TACC: CREATE_ENV_MODE env=${ENV_NAME} mode=environment_file"
		if [ ! -f "${ENV_FILE}" ]; then
			echo "TACC: ERROR - Environment file not found: ${ENV_FILE}"
			exit 1
		fi

		echo "Creating conda environment '${ENV_NAME}' from ${ENV_FILE}"
		conda env create -n "${ENV_NAME}" -f "${ENV_FILE}" --yes

		if [ -f "${COOKBOOK_WORKSPACE_DIR}/.binder/requirements.txt" ]; then
			echo "Installing shared requirements.txt into ${ENV_NAME}"
			conda run -n "${ENV_NAME}" python -m pip install --no-cache-dir -r "${COOKBOOK_WORKSPACE_DIR}/.binder/requirements.txt"
		fi

		if [ "${ENV_FILENAME}" = "h2iUTA.yaml" ]; then
			download_opera_setup_env
			timed_step "install_displacement_tools:${ENV_NAME}" install_displacement_tools "${ENV_NAME}"
		fi
	fi

	conda run -n "${ENV_NAME}" python -m ipykernel install \
		--user \
		--name "${ENV_NAME}" \
		--display-name "Python (${ENV_NAME})"
}

function delete_conda_environment() {
	local env_name="$1"
	local env_prefix="${WORK}/miniconda3/envs/${env_name}"

	if [ ! -d "${env_prefix}" ]; then
		echo "TACC: Conda environment ${env_name} not present; skipping remove"
		return 0
	fi

	echo "TACC: DELETE_ENV_START env=${env_name} prefix=${env_prefix}"
	rm -rf "${env_prefix}"
	echo "TACC: DELETE_ENV_DONE env=${env_name} prefix=${env_prefix}"
}
function handle_installation() {
    if [ "${UPDATE_CONDA_ENV}" = "true" ]; then
        timed_step "delete_conda_environment:${COOKBOOK_CONDA_ENV}" delete_conda_environment "${COOKBOOK_CONDA_ENV}"
        timed_step "delete_conda_environment:h2iUTA" delete_conda_environment "h2iUTA"
        
        # Launch all 3 in the background
        timed_step "create_conda_environment:${COOKBOOK_CONDA_ENV}" create_conda_environment environment.yml "${COOKBOOK_CONDA_ENV}" &
        timed_step "create_conda_environment:h2iUTA" create_conda_environment h2iUTA.yaml "h2iUTA"
        # create_conda_environment werc.yaml "werc" 
        
        # Wait for all background processes to finish
        wait
        
    else
        needs_wait=false

        if ! { conda_environment_exists "${COOKBOOK_CONDA_ENV}"; } >/dev/null 2>&1; then
            timed_step "create_conda_environment:${COOKBOOK_CONDA_ENV}" create_conda_environment environment.yml "${COOKBOOK_CONDA_ENV}" &
            needs_wait=true
        else
            echo "Conda environment ${COOKBOOK_CONDA_ENV} already exists"
        fi

        if ! { conda_environment_exists "h2iUTA"; } >/dev/null 2>&1; then
            timed_step "create_conda_environment:h2iUTA" create_conda_environment h2iUTA.yaml "h2iUTA"
        else
            echo "Conda environment h2iUTA already exists"
        fi

        # create_conda_environment werc.yaml "werc"
        if [ "${needs_wait}" = "true" ]; then
            wait
        fi
    fi
}



#Execution
install_conda
if [ "$IS_GPU_JOB" = "true" ]; then
	load_cuda
fi
export_repo_variables
init_directory
init_timing_log
load_tap_functions
get_tap_certificate
get_tap_token
create_jupyter_configuration
handle_installation
timed_step "install_ckan_jupyter_extension:${COOKBOOK_CONDA_ENV}" install_ckan_jupyter_extension

run_jupyter
port_fowarding
send_url_to_webhook
session_cleanup
