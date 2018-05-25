#!/bin/bash

if [[ $TRAVIS_PYTHON_VERSION == "3.6" ]]; then
   #make_docs()
   echo TRUE
fi

make_docs() {
# create python virtual env
pip install sphinx sphinx_rtd_theme

# Automatically create code documentation
sphinx-apidoc -f -o hier_config ../../hier_config

# Remove exisitng code table of contents
if [ -f hier_config.rst ]; then
    rm hier_config.rst
fi

# Create a new code table of contents
cat > hier_config.rst << EOF
.. _hier_config:

==================
Code Documentation
==================

.. toctree::
   :maxdepth: 1

   hier_config/modules.rst

EOF

# Create the html files
make clean
make dirhtml

# Sync generated documentation to viewable path
rsync -avz --exclude sphinx-env "${PWD}/_build/dirhtml/" "../../docs"

exit 0
}
