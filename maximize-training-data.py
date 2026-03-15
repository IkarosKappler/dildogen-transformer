# How to Maximize 10k Pairs
# The key is aggressive data augmentation, since you can't easily get more data. Here's what works well for this task:
# Geometric augmentations (apply identically to both input and target):

import albumentations as A

joint_transform = A.Compose([
    A.HorizontalFlip(p=0.5),
    A.RandomRotate90(p=0.5),
    A.ShiftScaleRotate(shift_limit=0.1, scale_limit=0.2, rotate_limit=30, p=0.7),
    A.RandomCrop(height=224, width=224, p=0.5),
], additional_targets={"xyz_map": "image"})  # applies same transform to both



# Input-only augmentations (line drawing only, NOT the XYZ target):
pythoninput_only_transform = A.Compose([
    A.GaussNoise(p=0.3),
    A.RandomBrightnessContrast(p=0.3),
    A.Blur(blur_limit=3, p=0.2),
    A.ElasticTransform(p=0.2),  # simulates different drawing styles
])

## Recommended Approach for 10k Pairs

# Given your dataset size, here's a pragmatic training strategy:
# ```
# 1. Start small        → Train a U-Net at 256×256 as a baseline
# 2. Measure quickly    → Evaluate after ~20 epochs to check if it's learning
# 3. Add augmentation   → If overfitting, increase augmentation strength
# 4. Scale up           → Only move to larger models/resolution once baseline works
