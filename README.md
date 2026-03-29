# First run: install everything
```bash
> python3 -m venv .venv
> source .venv/bin/activate
> python3 -m pip install -r requirements.txt
```

# Train my model
```bash
> source .venv/bin/activate
> python3 lightning-setup.py
```

# To leave the python virtual environment
```bash
> deactivate
```

# Folder structure
```
dildogen-transformer/
├── classes/dataset.py
├── node-store-server/
│   ├── src/…
│   ├── uploads/
│   │   └── 2026/03/
│   │            ├── preview2d/…    # These are the 2D line drawings
│   │            ├── preview3d/…    # These are just 3d screeshots for convenience
│   │            └── sculptmap/…    # These are the RGB coded XYZ data files
│   └── views/…
…  …
├── README.md
…  …
```
