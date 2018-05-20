#!/bin/sh

# create python virtual env
#python3 -m venv sphinx-env
#source ./sphinx-env/bin/activate
#../../setup.py install
pip3 install sphinx sphinx_rtd_theme

# Automatically create code documentation
sphinx-apidoc -f -o hier_config ../../hier_config

# Remove exisitng code table of contents
if [ -f hier_config.rst ]; then
    rm hier_config.rst
fi

# Create a new code table of contents
cat > hier_config.rst << EOF
.. _hier_config:

=============================================
Hierarchical Configuration Code Documentation
=============================================

.. toctree::
   :maxdepth: 1

EOF

for i in `ls hier_config`; do
  echo "   hier_config/$i" >> hier_config.rst
done

# Create the html files
make clean
make dirhtml

# Sync generated documentation to viewable path
rsync -avz --exclude sphinx-env "${PWD}/_build/dirhtml/" "../../docs"

# remove python env
#deactivate
#rm -rf ./sphinx-env

exit 0
