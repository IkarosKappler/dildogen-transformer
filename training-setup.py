# Pseudocode outline
model = UNet(in_channels=1, out_channels=3)
optimizer = torch.optim.AdamW(model.parameters(), lr=2e-4)
scheduler = CosineAnnealingLR(optimizer, T_max=epochs)

for epoch in range(epochs):
    for line_drawing, xyz_map in dataloader:
        pred = model(line_drawing)          # [B, 3, H, W]
        loss = combined_loss(pred, xyz_map)
        loss.backward()
        optimizer.step()
        