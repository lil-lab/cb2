dnctl pipe 1 config bw 10MByte/s plr 0.05 delay 100ms
dnctl pipe 2 config bw 10MByte/s plr 0.05 delay 100ms
pfctl -E
pfctl -f rules.txt
