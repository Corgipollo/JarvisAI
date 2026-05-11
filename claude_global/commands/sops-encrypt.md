Encripta archivos con secretos usando SOPS + age.

Workflow:
1. Si no existe key age, crear una: `age-keygen -o ~/.config/sops/age/keys.txt`
2. Encriptar: `sops --encrypt --age AGE_PUBLIC_KEY archivo > archivo.enc`
3. Desencriptar: `sops --decrypt archivo.enc`
4. Editar in-place: `sops archivo.enc`

Si el usuario da un archivo, encriptarlo. Si dice "desencriptar", desencriptarlo. Si dice "setup", crear la key age y el .sops.yaml de configuracion.

Nunca mostrar la private key de age en el output.

$ARGUMENTS