#!/bin/bash

# @date     2022-11-04 (adapted from an earlier script)
# @modified 2025-08-19 For new image format 822x822 without safe area.
# @author   Ika

 

# Define some colors
_RED='\033[0;31m'
_GREEN='\033[0;32m'
_PURPLE='\033[0;35m'
_GREY="\033[0;37m"
_NC='\033[0m'

if [ $# -eq 0 ]
  then
    echo -e "${_RED}   No arguments supplied${_NC}"
    echo -e "${_PURPLE}   Please specifiy the input directory${_NC}"
    exit 1
fi


dirname="$1"
if [ ! -d "$dirname" ]; then
	echo -e "${_RED}   The directory '$dirname' could not be found.${_NC}"
    echo -e "${_PURPLE}   Please specifiy the input directory${_NC}"
    exit 1
fi

if ! command -v convert >/dev/null 2>&1
then
    echo "'convert' command could not be found. Please install imagemagick first."
    exit 1
fi

function remove_trailing_slash {
    path=$1
    length=${#path}
    last_char=${path:length-1:1}
    [[ $last_char == "/" ]] && path=${path:0:length-1}; :
    echo $path
}

dirname_notrailingslash=$(remove_trailing_slash $dirname)
dirname_out="${dirname_notrailingslash}-out"


function process_directory {

    _dirname="$1"
    _dirname_out="$2"
    if [ ! -d "$_dirname" ]; then
        echo -e "${_RED}   The directory '$_dirname' could not be found.${_NC}"
        echo -e "${_PURPLE}   Please specifiy the input directory${_NC}"
        exit 1
    else

        if [ ! -d "$_dirname_out" ]; then
            echo -e "${_GREEN}   Creating output directory '$_dirname_out'.${_NC}"
            mkdir "$_dirname_out"
        else
            echo -e "${_GREEN}   Output directory '$_dirname_out' exists, no need to create.${_NC}"
        fi

        # Remove trailing slash so we can just process without caring if it's there
        _dirname=$(remove_trailing_slash $_dirname)

        # Iterate through all large start-JPG files.
        # for file in "$_dirname/"*.{jpg,JPG,jpeg,JPEG,png,PNG}; do 
        for file in "$_dirname/"*.{png,PNG}; do
        
            echo "FILE: $file"
            filename=$(basename "$file")

            if [ ! -f "$file" ]; then
                echo -e "${_GREY}   Skipping non-regular file '$_dirname/$filename'.${_NC}"
            elif [[ $file == *"_thumb.jpg"* ]]; then
                echo -e "${_PURPLE}   Skipping old thumbnail format '$_dirname/$filename'.${_NC}"
            else     
                # Get the file name without extension
                prefix="${filename%%.*}"
                # Replace the '832x822' by '822x822'
                # prefix=${prefix/832x822/822x822}
                # Extract the extension
                extension="${filename##*.}"
                echo -e "${_GREEN}   Output directory: $_dirname_out${_NC}"
                echo -e "${_GREY}   Prefix: $prefix${_NC}"
                echo -e "${_GREY}   Extension: $extension${_NC}"

                echo -e "   ${_PURPLE}Generating Resized file${_NC}"
                # convert "$file" -crop 472x472+180+350 -scale 822x822 -quality 100 "$_dirname_out/$prefix-cropped.$extension"
                # convert "$file" "$_dirname_out/$prefix.png"
                convert "$file" -resize 256x256\! "$_dirname_out/$prefix.png"

                echo -e "   ${_GREEN}Done.${_NC}"
            fi
        done # END for

        # Now process sub directories
        for file in "$_dirname/"*; do 
            if [ -d "$file" ]; then
                echo "DIRECTORY $file"
                filename=$(basename "$file")
                echo "filename: $filename"
                _dirname_out="$2" # re-fetch (might have been altered in recursion)
                echo -e "${_PURPLE}    Process recursively '$file', output dir is '$_dirname_out/$filename'.${_NC}"
                (process_directory "$file" "$_dirname_out/$filename")
            fi
        done # END for
    fi # END else
}

process_directory "$dirname" "$dirname_out"


