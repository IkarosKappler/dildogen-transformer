#!/bin/bash

bash ./node-store-server/image-check-format.sh ./node-store-server/uploads/2026/03/sculptmap2
bash ./node-store-server/image-check-format.sh ./node-store-server/uploads/2026/03/preview2d

# python3 lightning-setup.py

# python train.py --data_root ./data --epochs 200 --batch_size 16
# python train.py --data_root ./data --resume checkpoints/last.pt


python3 train.py  --data_root ./node-store-server/uploads/2026/03/ --epochs 200 --batch_size 16
