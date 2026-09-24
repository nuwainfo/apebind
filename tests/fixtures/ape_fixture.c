#define _POSIX_C_SOURCE 200809L

#include <ctype.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static volatile sig_atomic_t g_running = 1;

static void stop_handler(int signal_number) {
    (void)signal_number;
    g_running = 0;
}

static void print_root_help(void) {
    puts("usage: ape-fixture [-h] [--verbose] {echo,math,serve,json,fail} ...");
    puts("");
    puts("Fixture APE for APEBind integration tests.");
    puts("");
    puts("positional arguments:");
    puts("  {echo,math,serve,json,fail}");
    puts("    echo                Echo text.");
    puts("    math                Math operations.");
    puts("    serve               Run until terminated.");
    puts("    json                Emit structured JSON.");
    puts("    fail                Exit with a requested error code.");
    puts("");
    puts("options:");
    puts("  -h, --help            show this help message and exit");
    puts("  --verbose             Enable verbose output.");
}

static void print_echo_help(void) {
    puts("usage: ape-fixture echo [-h] [--upper] [--repeat REPEAT] text [text ...]");
    puts("");
    puts("positional arguments:");
    puts("  text                  Text values to echo.");
    puts("");
    puts("options:");
    puts("  -h, --help            show this help message and exit");
    puts("  --upper               Uppercase the text.");
    puts("  --repeat REPEAT       Repeat count.");
}

static void print_math_help(void) {
    puts("usage: ape-fixture math [-h] {add,multiply} ...");
    puts("");
    puts("positional arguments:");
    puts("  {add,multiply}");
    puts("    add                 Add two integers.");
    puts("    multiply            Multiply two integers.");
    puts("");
    puts("options:");
    puts("  -h, --help            show this help message and exit");
}

static void print_math_leaf_help(const char *command_name) {
    printf("usage: ape-fixture math %s [-h] left right\n", command_name);
    puts("");
    puts("positional arguments:");
    puts("  left                  Left integer.");
    puts("  right                 Right integer.");
    puts("");
    puts("options:");
    puts("  -h, --help            show this help message and exit");
}

static void print_serve_help(void) {
    puts("usage: ape-fixture serve [-h] [--json PATH] [--message MESSAGE]");
    puts("");
    puts("options:");
    puts("  -h, --help            show this help message and exit");
    puts("  --json PATH           Write startup JSON to this file.");
    puts("  --message MESSAGE     Message included in startup JSON.");
}


static void print_json_help(void) {
    puts("usage: ape-fixture json [-h] [--value VALUE]");
    puts("");
    puts("options:");
    puts("  -h, --help            show this help message and exit");
    puts("  --value VALUE         Value to include in JSON.");
}

static void print_fail_help(void) {
    puts("usage: ape-fixture fail [-h] [--code COUNT]");
    puts("");
    puts("options:");
    puts("  -h, --help            show this help message and exit");
    puts("  --code COUNT          Exit code to return.");
}

static int is_help_argument(const char *value) {
    return strcmp(value, "--help") == 0 || strcmp(value, "-h") == 0;
}

static int handle_echo(int argc, char **argv) {
    int upper = 0;
    int repeat = 1;
    const char *values[64];
    int value_count = 0;

    for (int index = 0; index < argc; index++) {
        const char *value = argv[index];
        if (is_help_argument(value)) {
            print_echo_help();
            return 0;
        }
        if (strcmp(value, "--upper") == 0) {
            upper = 1;
            continue;
        }
        if (strcmp(value, "--repeat") == 0) {
            if (index + 1 >= argc) {
                fputs("--repeat requires a value\n", stderr);
                return 2;
            }
            repeat = atoi(argv[++index]);
            continue;
        }
        if (value_count >= 64) {
            fputs("too many echo values\n", stderr);
            return 2;
        }
        values[value_count++] = value;
    }

    if (value_count == 0) {
        fputs("echo requires text\n", stderr);
        return 2;
    }

    for (int repetition = 0; repetition < repeat; repetition++) {
        for (int value_index = 0; value_index < value_count; value_index++) {
            const char *value = values[value_index];
            if (value_index > 0) {
                putchar(' ');
            }
            for (size_t char_index = 0; char_index < strlen(value); char_index++) {
                int character = (unsigned char)value[char_index];
                putchar(upper ? toupper(character) : character);
            }
        }
        putchar('\n');
    }
    return 0;
}

static int handle_math(int argc, char **argv) {
    if (argc == 0 || is_help_argument(argv[0])) {
        print_math_help();
        return 0;
    }

    const char *command_name = argv[0];
    if (argc >= 2 && is_help_argument(argv[1])) {
        if (strcmp(command_name, "add") == 0 || strcmp(command_name, "multiply") == 0) {
            print_math_leaf_help(command_name);
            return 0;
        }
    }

    if (argc != 3) {
        fputs("math operation requires left and right integers\n", stderr);
        return 2;
    }

    long left = strtol(argv[1], NULL, 10);
    long right = strtol(argv[2], NULL, 10);
    if (strcmp(command_name, "add") == 0) {
        printf("%ld\n", left + right);
        return 0;
    }
    if (strcmp(command_name, "multiply") == 0) {
        printf("%ld\n", left * right);
        return 0;
    }
    fprintf(stderr, "unknown math command: %s\n", command_name);
    return 2;
}

static int handle_serve(int argc, char **argv) {
    const char *json_path = NULL;
    const char *message = "ready";

    for (int index = 0; index < argc; index++) {
        const char *value = argv[index];
        if (is_help_argument(value)) {
            print_serve_help();
            return 0;
        }
        if (strcmp(value, "--json") == 0) {
            if (index + 1 >= argc) {
                fputs("--json requires a path\n", stderr);
                return 2;
            }
            json_path = argv[++index];
            continue;
        }
        if (strcmp(value, "--message") == 0) {
            if (index + 1 >= argc) {
                fputs("--message requires a value\n", stderr);
                return 2;
            }
            message = argv[++index];
            continue;
        }
        fprintf(stderr, "unknown serve argument: %s\n", value);
        return 2;
    }

    if (json_path == NULL) {
        fputs("--json is required\n", stderr);
        return 2;
    }

    FILE *output_file = fopen(json_path, "w");
    if (output_file == NULL) {
        perror("fopen");
        return 2;
    }
    fprintf(output_file, "{\"link\":\"https://example.test/%s\"}", message);
    fclose(output_file);

    puts("ready");
    fflush(stdout);
    signal(SIGTERM, stop_handler);
    signal(SIGINT, stop_handler);
    const struct timespec sleep_interval = {.tv_sec = 0, .tv_nsec = 50000000};
    while (g_running) {
        nanosleep(&sleep_interval, NULL);
    }
    puts("stopped");
    fflush(stdout);
    return 0;
}


static int handle_json(int argc, char **argv) {
    const char *value = "default";
    for (int index = 0; index < argc; index++) {
        const char *argument = argv[index];
        if (is_help_argument(argument)) {
            print_json_help();
            return 0;
        }
        if (strcmp(argument, "--value") == 0) {
            if (index + 1 >= argc) {
                fputs("--value requires a value\n", stderr);
                return 2;
            }
            value = argv[++index];
            continue;
        }
        fprintf(stderr, "unknown json argument: %s\n", argument);
        return 2;
    }
    printf("{\"payload\":{\"value\":\"%s\"}}\n", value);
    return 0;
}

static int handle_fail(int argc, char **argv) {
    int exit_code = 7;
    for (int index = 0; index < argc; index++) {
        const char *value = argv[index];
        if (is_help_argument(value)) {
            print_fail_help();
            return 0;
        }
        if (strcmp(value, "--code") == 0) {
            if (index + 1 >= argc) {
                fputs("--code requires a value\n", stderr);
                return 2;
            }
            exit_code = atoi(argv[++index]);
            continue;
        }
        fprintf(stderr, "unknown fail argument: %s\n", value);
        return 2;
    }
    fprintf(stderr, "requested failure %d\n", exit_code);
    return exit_code;
}

int main(int argc, char **argv) {
    if (argc <= 1 || is_help_argument(argv[1])) {
        print_root_help();
        return 0;
    }

    int argument_index = 1;
    if (strcmp(argv[argument_index], "--verbose") == 0) {
        argument_index++;
    }
    if (argument_index >= argc) {
        print_root_help();
        return 0;
    }

    const char *command_name = argv[argument_index++];
    int remaining_count = argc - argument_index;
    char **remaining_values = argv + argument_index;

    if (strcmp(command_name, "echo") == 0) {
        return handle_echo(remaining_count, remaining_values);
    }
    if (strcmp(command_name, "math") == 0) {
        return handle_math(remaining_count, remaining_values);
    }
    if (strcmp(command_name, "serve") == 0) {
        return handle_serve(remaining_count, remaining_values);
    }
    if (strcmp(command_name, "json") == 0) {
        return handle_json(remaining_count, remaining_values);
    }
    if (strcmp(command_name, "fail") == 0) {
        return handle_fail(remaining_count, remaining_values);
    }

    fprintf(stderr, "unknown command: %s\n", command_name);
    return 2;
}
