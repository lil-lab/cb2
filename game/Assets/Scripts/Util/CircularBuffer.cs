using System;
using UnityEngine;

namespace Util 
{

public class CircularBuffer
{
    private int _capacity;
    private int _size;
    private int _head;  // Where data enters (Enqueue).
    private int _tail;  // Where data leaves (Dequeue).
    private byte[] _buffer;

    public CircularBuffer(int capacity)
    {
        _buffer = new byte[capacity];
        _capacity = capacity;
        _head = 0;
        _tail = 0;
        _size = 0;
    }

    public bool Empty()
    {
        return _size == 0;
    }

    public bool Full()
    {
        return _size == _capacity;
    }

    public int Size()
    {
        return _size;
    }

    public byte Peek()
    {
        return _buffer[_tail];
    } 

    public bool Enqueue(byte item)
    {
        if (Full()) return false;
        _buffer[_head] = item;
        _head = (_head + 1) % _capacity;
        _size += 1;
        return true;
    }

    public byte? Dequeue()
    {
        if (Empty()) return null;
        byte item = _buffer[_tail];
        _tail = (_tail + 1) % _capacity;
        _size -= 1;
        return item;
    }

    public bool EnqueueString(string item)
    {
        byte[] data = System.Text.Encoding.UTF8.GetBytes(item.ToCharArray());
        if (item.Length == 0) return false;
        if (_capacity - Size() < item.Length) return false;
        if (_head >= _tail)
        {
            if (_capacity - _head > item.Length)
            {
                // Fits in one block.
                Array.Copy(data, 0, _buffer, _head, item.Length);
                _head = (_head + item.Length) % _capacity;
                _size += item.Length;
                return true;
            } else {
                // Fits in two blocks.
                Array.Copy(data, 0, _buffer, _head, _capacity - _head);
                Array.Copy(data, _capacity - _head, _buffer, 0, item.Length - _capacity + _head);
                _head = (_head + item.Length) % _capacity;
                _size += item.Length;
                return true;
            }
        } else if (_tail > _head)
        {
            // Fits in one block.
            Array.Copy(data, 0, _buffer, _head, item.Length);
            _head = (_head + item.Length) % _capacity;
            _size += item.Length;
            return true;
        }
        return false;
    }
}

} // namespace Util