#!/usr/bin/bash

THIS=$(basename $0)
HERE=$(dirname $0)

# cleanup temporary files upon exit of this script
cleanup() {
  rv=$?
  if [ -d "$GIT_REPO" ]; then
    rm -rf $GIT_REPO
  fi
  exit $rv
}
trap cleanup EXIT

help() {
  echo "usage: git_checkout_and_run_JSONs.py [-h|--help]"
  echo "                                     [--CIBSE-weather-file CIBSE_WEATHER_FILE]"
  echo "                                     repo_path folder_path"
  echo ""
  echo "Script to run previous versions of HEM"
  echo ""
  echo "positional arguments:"
  echo "  repo_path             path to your personal HEM repository"
  echo "  folder_path           path to folder containing sub-folders named after"
  echo "                        commit IDs and holding relevant input JSONs"
  echo ""
  echo "options:"
  echo "  -h, --help            show this help message and exit"
  echo "  --CIBSE-weather-file CIBSE_WEATHER_FILE"
  echo "                        path to CIBSE weather file in .csv format"
  echo "  --epw-file EPW_FILE   path to EPW weather file in .csv format"
}

POSITIONAL_ARGS=()

while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help)
      help
      exit 0
      ;;
    --CIBSE-weather-file)
      CIBSE_WEATHER_FILE="$2"
      shift # past argument
      shift # past value
      ;;
    --epw-file)
      EPW_WEATHER_FILE="$2"
      shift # past argument
      shift # past value
      ;;
    -*|--*)
      echo "Unknown option $1"
      exit 1
      ;;
    *)
      POSITIONAL_ARGS+=("$1") # save positional arg
      shift # past argument
      ;;
  esac
done

if [ ${#POSITIONAL_ARGS[*]} != 2 ]; then
  help
  exit 1
fi

if [ -n "$CIBSE_WEATHER_FILE" -a -n "$EPW_WEATHER_FILE" ]; then
  echo "Only one of --CIBSE-weather-file or --epw-file may be specified"
  help
  exit 1
fi 

PATH_TO_REPO=${POSITIONAL_ARGS[0]}
PATH_TO_FOLDER=${POSITIONAL_ARGS[1]}

if [ -n "$CIBSE_WEATHER_FILE" -a ! -f "$CIBSE_WEATHER_FILE" ]; then
  echo "The file $CIBSE_WEATHER_FILE cannot be found"
  exit 1
fi
if [ -n "$EPW_WEATHER_FILE" -a ! -f "$EPW_WEATHER_FILE" ]; then
  echo "The file $EPW_WEATHER_FILE cannot be found"
  exit 1
fi

read -p "Before files get rerun, are you confident they are appropriately set up for the relevant commit IDs? (yes/no): " confirm && [[ $confirm == 'yes' ]] || exit 1

# setup a temporary git clone directory
GIT_REPO=/tmp/tmp.$$
mkdir $GIT_REPO
# Note SAP%2011 means the same as "SAP 11" (the space needs to be encoded to keep git happy)
(cd $GIT_REPO; git clone "git@ssh.dev.azure.com:v3/BreGroup/SAP%2011/SAP%2011")
PATH_TO_GIT_REPO="$GIT_REPO/SAP%2011"

# Activate the Python virtual environment
if [ -d $PATH_TO_REPO/venv/bin/activate ]; then
  # Linux only
  . $PATH_TO_REPO/venv/bin/activate
fi
if [ -d $PATH_TO_REPO/venv/Scripts/activate ]; then
  # Windows only
  . $PATH_TO_REPO/venv/Scripts/activate
fi

for COMMIT_ID in $(ls $PATH_TO_FOLDER)
do
  echo "Processing commit id: $COMMIT_ID"
  # Checkout a specific commit id and work with that release of the code
  (cd $PATH_TO_GIT_REPO; git checkout $COMMIT_ID)
  for FILE in $(ls $PATH_TO_FOLDER/$COMMIT_ID)
  do
    PATH_TO_FILE=$PATH_TO_FOLDER/$COMMIT_ID/$FILE
    echo "Processing HEM file: $PATH_TO_FILE"
    # Run HEM with either the CIBSE or the EPW weather file
    if [ -n "$CIBSE_WEATHER_FILE" ]; then
      # Run HEM both with and without the FHS wrapper
      python $PATH_TO_GIT_REPO/src/hem.py $PATH_TO_FILE --CIBSE-weather-file "$CIBSE_WEATHER_FILE" --heat-balance --detailed-output-heating-cooling
      python $PATH_TO_GIT_REPO/src/hem.py $PATH_TO_FILE --CIBSE-weather-file "$CIBSE_WEATHER_FILE" --heat-balance --future-homes-standard
    elif [ -n "$EPW_WEATHER_FILE" ]; then
      # Run HEM both with and without the FHS wrapper
      python $PATH_TO_GIT_REPO/src/hem.py $PATH_TO_FILE --epw-file "$EPW_WEATHER_FILE" --heat-balance --detailed-output-heating-cooling
      python $PATH_TO_GIT_REPO/src/hem.py $PATH_TO_FILE --epw-file "$EPW_WEATHER_FILE" --heat-balance --future-homes-standard
    fi
  done
done
