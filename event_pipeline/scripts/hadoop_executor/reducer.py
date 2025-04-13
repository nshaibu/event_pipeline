#!/usr/bin/env python
import sys
import pickle


def reduce_collect():
    results = []
    errors = []

    for line in sys.stdin:
        key, value = line.strip().split('\t', 1)
        value = pickle.loads(value.encode('utf-8'))

        if key == "result":
            results.append(value)
        elif key == "error":
            errors.append(value)

    # If any errors occurred, output the first one
    if errors:
        output = errors[0]
    else:
        # Otherwise, output the results
        output = results

    # Write the final result
    sys.stdout.buffer.write(pickle.dumps(output))


if __name__ == "__main__":
    reduce_collect()

