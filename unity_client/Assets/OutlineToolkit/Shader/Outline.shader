Shader "OutlineToolkit/Outline"
{
	Properties
	{
		_OutlineColor ("OutlineColor", Color) = (0, 0, 0, 1)
		_Width ("Width", float) = 2
	}
		SubShader
	{
		Tags { "RenderType" = "Opaque" }
		LOD 100

		Pass
		{
			Name "OUTLINE"

			Cull Front
			CGPROGRAM
			#pragma vertex vert
			#pragma fragment frag
			// make fog work
			#pragma multi_compile_fog

			#include "UnityCG.cginc"

			struct appdata
			{
				float4 vertex : POSITION;
				float4 normal: NORMAL;
			};

			struct v2f
			{
				UNITY_FOG_COORDS(1)
				float4 vertex : SV_POSITION;
			};

			float _Width;
			float4 _OutlineColor;
			
			v2f vert (appdata v)
			{
				v2f o;

				if (_Width == 0)
					_Width = 2;

				float3 cameraForwardWorld = mul((float3x3)unity_CameraToWorld, float3(0, 0, 1));
				float3 cameraForwardObject = mul((float3x3)unity_WorldToObject, cameraForwardWorld);

				float3 tangent = cross(cameraForwardObject, v.normal);
				float3 projectedNormal = cross(cameraForwardObject, tangent);

				projectedNormal = normalize(-projectedNormal) * _Width * length(mul(unity_ObjectToWorld, v.vertex) - _WorldSpaceCameraPos) / max(_ScreenParams.x, _ScreenParams.y);

				v.vertex += float4(projectedNormal, 0);

				o.vertex = UnityObjectToClipPos(v.vertex);
				UNITY_TRANSFER_FOG(o,o.vertex);
				return o;
			}
			
			fixed4 frag (v2f i) : SV_Target
			{
				fixed4 col = _OutlineColor;
				UNITY_APPLY_FOG(i.fogCoord, col);
				return col;
			}
			ENDCG
		}
	}
}
