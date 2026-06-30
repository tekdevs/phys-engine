# -- Project information -----------------------------------------------------
project = 'Phys Engine'

# The short X.Y version
version = '0.1'
# The full version, including alpha/beta/rc tags

# -- General configuration ---------------------------------------------------
# Add any Sphinx extension module names here, as strings.
extensions = [
    'sphinx.ext.autodoc',      # Core library for pulling docstrings from your code
    'sphinx.ext.napoleon',     # Support for Google or NumPy style docstrings
    'sphinx.ext.viewcode',     # Adds links to highlighted source code
]

# The master toctree document (usually index.rst or index.md)
master_doc = 'index'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------
# The theme to use for HTML and HTML Help pages.
html_theme = 'sphinx_rtd_theme'
