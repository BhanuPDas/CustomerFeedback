package de.fh_dortmund.inference.domain.component;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Metrics;
import io.micrometer.core.instrument.Tags;
import io.micrometer.core.instrument.binder.MeterBinder;
import lombok.Getter;

@Component
@Getter
public class CustomMetricsBinder implements MeterBinder {

	private volatile long latency;
	private volatile float feedbackScore;
	private volatile float accuracy;
	private volatile float cpuUtilization;
	private volatile float ramUsage;
	private volatile int cpuCycle;
	private final Counter requestCount;

	public CustomMetricsBinder(MeterRegistry meterRegistry, @Value("${app.env:local}") String env) {
		meterRegistry.gauge("latency", Tags.of("env", env), this, CustomMetricsBinder::getLatency);
		meterRegistry.gauge("feedback_score", Tags.of("env", env), this, CustomMetricsBinder::getFeedbackScore);
		meterRegistry.gauge("accuracy", Tags.of("env", env), this, CustomMetricsBinder::getAccuracy);
		meterRegistry.gauge("cpu_utilization", Tags.of("env", env), this, CustomMetricsBinder::getCpuUtilization);
		meterRegistry.gauge("ram_usage", Tags.of("env", env), this, CustomMetricsBinder::getRamUsage);
		meterRegistry.gauge("cpu_cycle", Tags.of("env", env), this, CustomMetricsBinder::getCpuCycle);
		this.requestCount = Counter.builder("request_count").tags("env", env).description("Total count of requests")
				.register(Metrics.globalRegistry);
	}

	public void updateMetrics(long latency, float feedbackScore, float accuracy, float cpuUtilization,
			float ramUsage, int cpuCycle) {
		this.latency = latency;
		this.feedbackScore = feedbackScore;
		this.accuracy = accuracy;
		this.cpuUtilization = cpuUtilization;
		this.ramUsage = ramUsage;
		this.cpuCycle = cpuCycle;
	}

	@Override
	public void bindTo(MeterRegistry registry) {
	}
	
	public void incrementRequestCount() {
        requestCount.increment();
    }
}
