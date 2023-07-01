using System.Collections;
using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;

public class CircularBufferTests
{
    // A Test behaves as an ordinary method
    [Test]
    public void CircularBufferTestsSimple()
    {
        // Use the Assert class to test conditions
        Util.CircularBuffer buffer = new Util.CircularBuffer(10);
        Assert.AreEqual(0, buffer.Size());
        Assert.AreEqual(true, buffer.Empty());
        Assert.AreEqual(false, buffer.Full());
    }

    [Test]
    public void CircularBufferTestsEnqueue()
    {
        // Use the Assert class to test conditions
        Util.CircularBuffer buffer = new Util.CircularBuffer(10);
        Assert.AreEqual(0, buffer.Size());
        Assert.AreEqual(true, buffer.Empty());
        Assert.AreEqual(false, buffer.Full());
        Assert.AreEqual(true, buffer.Enqueue(1));
        Assert.AreEqual(false, buffer.Empty());
    }

    [Test]
    public void CircularBufferTestsDequeue()
    {
        // Use the Assert class to test conditions
        Util.CircularBuffer buffer = new Util.CircularBuffer(10);
        Assert.AreEqual(0, buffer.Size());
        Assert.AreEqual(true, buffer.Empty());
        Assert.AreEqual(false, buffer.Full());
        Assert.AreEqual(true, buffer.Enqueue(1));
        Assert.AreEqual(false, buffer.Empty());
        byte? val = buffer.Dequeue();
        Assert.NotNull(val);
        Assert.AreEqual(1, val);
        Assert.True(buffer.Empty());
        Assert.AreEqual(0, buffer.Size());
    }

    [Test]
    public void CircularBufferTestsFillTest()
    {
        // Use the Assert class to test conditions
        Util.CircularBuffer buffer = new Util.CircularBuffer(10);
        Assert.AreEqual(0, buffer.Size());
        Assert.AreEqual(true, buffer.Empty());
        Assert.AreEqual(false, buffer.Full());
        for (int i = 0; i < 10; ++i)
        {
            Assert.AreEqual(i, buffer.Size());
            Assert.AreEqual(true, buffer.Enqueue((byte)i));
            Assert.AreEqual(false, buffer.Empty());
        }
        Assert.True(buffer.Full());
        Assert.AreEqual(10, buffer.Size());
        for (int i = 0; i < 10; ++i)
        {
            byte? val = buffer.Dequeue();
            Assert.NotNull(val);
            Assert.AreEqual(i, val);
        }
        Assert.AreEqual(0, buffer.Size());
        Assert.True(buffer.Empty());
    }

    [Test]
    public void CircularBufferTestsStringEnqueueTest()
    {
        string A = "This is string A!\n";
        string B = "String B is in a different line.\n";
        string C = "You can't even compare it to string C!";
        Util.CircularBuffer buffer = new Util.CircularBuffer(100);

        buffer.EnqueueString(A);
        Assert.AreEqual(A.Length, buffer.Size());
        buffer.EnqueueString(B);
        Assert.AreEqual(A.Length + B.Length, buffer.Size());
        buffer.EnqueueString(C);
        Assert.AreEqual(A.Length + B.Length + C.Length, buffer.Size());

        string aRecreated = "";
        string bRecreated = "";
        string cRecreated = "";

        for (int i = 0; i < A.Length; ++i)
        {
            byte? val = buffer.Dequeue();
            Assert.NotNull(val);
            aRecreated += (char)val;
        }
        for (int i = 0; i < B.Length; ++i)
        {
            byte? val = buffer.Dequeue();
            Assert.NotNull(val);
            bRecreated += (char)val;
        }
        for (int i = 0; i < C.Length; ++i)
        {
            byte? val = buffer.Dequeue();
            Assert.NotNull(val);
            cRecreated += (char)val;
        }
        Assert.AreEqual(A, aRecreated);
        Assert.AreEqual(B, bRecreated);
        Assert.AreEqual(C, cRecreated);
    }

    [Test]
    public void CircularBufferTestsWraparoundTest()
    {
        Util.CircularBuffer buffer = new Util.CircularBuffer(10);
        for (int i = 0; i < 5; ++i)
        {
            Assert.AreEqual(i, buffer.Size());
            Assert.AreEqual(true, buffer.Enqueue((byte)i));
        }
        for (int i = 0; i < 5; ++i)
        {
            byte? val = buffer.Dequeue();
            Assert.NotNull(val);
            Assert.AreEqual(i, val);
        }
        for (int i = 0; i < 10; ++i)
        {
            Assert.AreEqual(i, buffer.Size());
            Assert.AreEqual(true, buffer.Enqueue((byte)i));
        }
        for (int i = 0; i < 10; ++i)
        {
            byte? val = buffer.Dequeue();
            Assert.NotNull(val);
            Assert.AreEqual(i, val);
        }
        Assert.AreEqual(0, buffer.Size());
    }

    [Test]
    public void CircularBufferStringWrapAroundTest()
    {
        Util.CircularBuffer buffer = new Util.CircularBuffer(10);
        string A = "ABCDE";
        string B = "ABCDEFGHIJ";
        Assert.True(buffer.EnqueueString(A));
        for (int i = 0; i < A.Length; ++i)
        {
            byte? val = buffer.Dequeue();
            Assert.NotNull(val);
            Assert.AreEqual(A[i], (char)val);
        }
        Assert.True(buffer.EnqueueString(B));
        for (int i = 0; i < B.Length; ++i)
        {
            byte? val = buffer.Dequeue();
            Assert.NotNull(val);
            Assert.AreEqual(B[i], (char)val);
        }
    }

    [Test]
    public void CircularBufferStringEnqueueWraparoundSingleCopy()
    {
        Util.CircularBuffer buffer = new Util.CircularBuffer(10);
        string A = "ABCDEFGHI";
        Assert.True(buffer.EnqueueString(A));
        for (int i = 0; i < A.Length; ++i)
        {
            byte? val = buffer.Dequeue();
            Assert.NotNull(val);
            Assert.AreEqual(A[i], (char)val);
        }
        string B = "ABC";
        Assert.True(buffer.EnqueueString(B));
        string C = "ABCDEFG";
        Assert.True(buffer.EnqueueString(C));
        Assert.True(buffer.Full());
        for (int i = 0; i < B.Length; ++i)
        {
            byte? val = buffer.Dequeue();
            Assert.NotNull(val);
            Assert.AreEqual(B[i], (char)val);
        }
        for (int i = 0; i < C.Length; ++i)
        {
            byte? val = buffer.Dequeue();
            Assert.NotNull(val);
            Assert.AreEqual(C[i], (char)val);
        }
    }
    [Test]
    public void CircularBufferNewlineEncodingTest()
    {
        // Tests what happens if you try to call toCharArray() on a string with a newline character.
        string test = "\n";
        char[] testCharArray = test.ToCharArray();
        Assert.AreEqual(1, testCharArray.Length);
    }
}
