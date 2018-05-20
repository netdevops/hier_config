#!/bin/bash

EXIT=0

pycodestyle --ignore E501 hier_config/

RC=$?
if [[ $RC != 0 ]]; then
    echo -e "\n$(info) one or more PEP 8 errors detected, failing build."
    EXIT=$RC
fi

exit $EXIT
