import groovy.json.JsonSlurper
import java.util.concurrent.TimeUnit

// The independently pinned product map is immutable runtime data. Native/APK
// acceptance is recorded separately after the actual build and output checks.
return { File picoRoot ->
    def process = new ProcessBuilder('python3',
        new File(picoRoot, 'native-ci/inputs.py').absolutePath).start()
    def output = new StringBuffer()
    def errors = new StringBuffer()
    def stdoutReader = process.consumeProcessOutputStream(output)
    def stderrReader = process.consumeProcessErrorStream(errors)
    if (!process.waitFor(600, TimeUnit.SECONDS)) {
        process.destroyForcibly()
        throw new IllegalStateException('PICO_CI_INPUTS_TIMEOUT')
    }
    stdoutReader.join()
    stderrReader.join()
    if (process.exitValue() != 0) {
        throw new IllegalStateException('PICO_CI_INPUTS_REJECTED')
    }
    def inputs = new JsonSlurper().parseText(output.toString())
    if (inputs.status != 'PICO_CI_INPUT_BYTES_BOUND_NATIVE_VERIFICATION_PENDING' ||
        inputs.pico_qualified != false) {
        throw new IllegalStateException('PICO_CI_INPUTS_STATUS')
    }
    inputs
}
