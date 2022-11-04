UNITY="/Applications/Unity/Hub/Editor/2020.3.25f1/Unity.app/Contents/MacOS/Unity"
$UNITY -quit -batchmode -logFile - -projectPath game/ -executeMethod WebGLBuilder.Build
rm -rf server/www/OLD_WebGL
mv server/www/WebGL server/www/OLD_WebGL
cp -rf game/builds/WebGLVersion server/www/WebGL
echo "Moved build to server/www directory"
