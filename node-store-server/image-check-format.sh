#!/bin/bash
#
# date 2026-04-06

 

source "./colors.sh"

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
# dirname_out="${dirname_notrailingslash}-out"


function process_directory {

    _dirname="$1"
    # _dirname_out="$2"
    if [ ! -d "$_dirname" ]; then
        echo -e "${_RED}   The directory '$_dirname' could not be found.${_NC}"
        echo -e "${_PURPLE}   Please specifiy the input directory${_NC}"
        exit 1
    else

        # if [ ! -d "$_dirname_out" ]; then
        #     echo -e "${_GREEN}   Creating output directory '$_dirname_out'.${_NC}"
        #     mkdir "$_dirname_out"
        # else
        #     echo -e "${_GREEN}   Output directory '$_dirname_out' exists, no need to create.${_NC}"
        # fi

        # Remove trailing slash so we can just process without caring if it's there
        _dirname=$(remove_trailing_slash $_dirname)

        # Prepare a spinner animation
        spin='-\|/'
        i=0

        # Iterate through all large start-JPG files.
        # for file in "$_dirname/"*.{jpg,JPG,jpeg,JPEG,png,PNG}; do 
        for file in "$_dirname/"*.{png,PNG}; do
        
            # echo "FILE: $file"
            filename=$(basename "$file")

            i=$(( (i+1) %4 ))
            printf "\r${spin:$i:1}"

            if [ ! -f "$file" ]; then
                echo -e "${_GREY}   Skipping non-regular file '$_dirname/$filename'.${_NC}"
            elif [[ $file == *"_thumb.jpg"* ]]; then
                echo -e "${_PURPLE}   Skipping old thumbnail format '$_dirname/$filename'.${_NC}"
            else     
                # Check file for correct format
                # echo -e "   ${_GREEN}Match.${_NC}"
                image_format_str=$(identify -ping -format "%wx%h\n" "$_dirname/$filename")
                if [ "$image_format_str" != "256x256" ]; then
                    echo "FILE: $file"
                    echo "Format: $image_format_str"
                    echo "Warning: image has wrong format!"

                    while true; do
                        read -p "Do you really wish to rename file $_dirname/$filename to *._CORRUPT (y/n/c)? " ync
                        case $yn in
                                [Yy]* ) mv "$_dirname/$filename" "$_dirname/$filename._CORRUPT"; break;;
                                [Nn]* ) break;;
                                [Cc]* ) exit;;
                                * ) echo "Please answer y or n or c.";;
                        esac
                    done
                fi
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


