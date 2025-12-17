from PIL import Image

img = Image.open("logopeq.png").convert("RGBA")

img_192 = img.resize((192, 192), Image.LANCZOS)
img_192.save("icon-192.png")

img_512 = img.resize((512, 512), Image.LANCZOS)
img_512.save("icon-512.png")
