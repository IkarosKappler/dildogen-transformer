
## Error
ValueError: Height and Width of image, mask or masks should be equal. You can disable shapes check by setting a parameter is_check_shapes=False of Compose class (do it only if you are sure about your data consistency).

-> Updates dataset.py #60
Insert following line:
`is_check_shapes=True,`

## Error: wrong training image sizes
It turns out the training image pairs must have the same image dimenions.
* Currently the preview2d/linedraw images are: 256x255
* Currently the sculptmap/3ddata images are: 128x256

-> Workaroung: use the resizer script 
`node-store-server/image-resize-to-256x256.sh uploads/2026/03/sculptmaps`

to resize them all.
