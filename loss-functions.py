# L1 / L2 on raw XYZ values
l1_loss = nn.L1Loss()(pred_xyz, target_xyz)

# Gradient loss (enforces smooth surfaces)
grad_loss = gradient_loss(pred_xyz, target_xyz)

# Normal consistency loss (surface normals derived from XYZ should match)
normal_loss = normal_consistency_loss(pred_xyz, target_xyz)

# Perceptual loss (optional, using VGG features)
perceptual_loss = VGGLoss()(pred_xyz, target_xyz)

total_loss = l1_loss + 0.5*grad_loss + 0.3*normal_loss
