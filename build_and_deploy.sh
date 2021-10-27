UNITY="/Applications/Unity/Hub/Editor/2020.3.19f1/Unity.app/Contents/MacOS/Unity"
$UNITY -quit -batchmode -logFile - -projectPath game/ -executeMethod WebGLBuilder.Build
cp -r game/builds/WebGLVersion server/www/WebGL
echo "Moved build to server/www directory"
