using System;
using UnityEngine;

namespace State
{ 
	public struct Continuous
	{
		public Vector3 Position;
	    public float HeadingDegrees;
		public float BorderRadius;
		public Network.Color BorderColor;
        public float Opacity;
		public ActionQueue.AnimationType Animation;
    }

	[Serializable]
	public struct Discrete
	{
		public HecsCoord Coord;
		public float HeadingDegrees;
		public float BorderRadius;
		public Network.Color BorderColor;
        public float Opacity;

		// If true, the asset should be removed from the world. Used to queue up
		// deallocation after an animation has occured.
		public bool EndOfLife;

	    public Vector3 Vector()
	    { 
			GameObject obj = GameObject.FindWithTag(HexGrid.TAG);
			HexGrid grid = obj.GetComponent<HexGrid>();

			(float x, float z) = Coord.Cartesian();
			return new Vector3(x, grid.Height(Coord), z);
	    }

		public Continuous Continuous()
		{
			return new Continuous()
			{
				Position = Vector(),
				HeadingDegrees = HeadingDegrees,
				BorderRadius = BorderRadius,
				BorderColor = BorderColor,
                Opacity = Opacity,
				Animation = ActionQueue.AnimationType.IDLE,
			};
		}
    }
}  // namespace State