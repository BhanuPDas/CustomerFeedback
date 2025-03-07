package de.fh_dortmund.inference.service.impl;

import java.time.Duration;
import java.time.Instant;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.client.RestTemplate;
import de.fh_dortmund.inference.beans.RequestIDMetrics;
import de.fh_dortmund.inference.domain.component.CustomMetricsBinder;
import de.fh_dortmund.inference.domain.request.InferenceRequest;
import de.fh_dortmund.inference.domain.response.InferenceResponse;
import de.fh_dortmund.inference.service.InferenceService;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;

@Service
public class InferenceServiceImpl implements InferenceService {

	Logger logger = LogManager.getLogger(InferenceServiceImpl.class);

	@Autowired
	private RestTemplate rest;
	@Autowired
	private CustomMetricsBinder metrics;
	@Value("${inference.url}")
	private String inferenceUrl;

	@Override
	public String analyseFeedback(InferenceRequest request) throws Exception {
		try {
			logger.info("Preparing request for inference:" + request.getText());
			HttpHeaders headers = new HttpHeaders();
			headers.setContentType(MediaType.APPLICATION_JSON);
			HttpEntity<InferenceRequest> inferenceEntity = new HttpEntity<InferenceRequest>(request, headers);
			Instant timeStart = Instant.now();
			ResponseEntity<InferenceResponse> response = rest.exchange(inferenceUrl, HttpMethod.POST, inferenceEntity,
					InferenceResponse.class);
			Instant timeEnd = Instant.now();
			long latency = Duration.between(timeStart, timeEnd).toMillis();
			logger.info("Latency of the request is: " + latency + "ms");
			if (response.getBody() != null) {
				RequestIDMetrics reqMetrics = new RequestIDMetrics();
				if (request.getId() != 0 && !response.getBody().getPodName().isBlank()) {
					reqMetrics.setRequestID(request.getId());
					reqMetrics.setPodName(response.getBody().getPodName());
					logger.info("*** Request ID: " + request.getId() + "has been processed by pod :"
							+ response.getBody().getPodName() + " ***");
				}
				addMetrics(response.getBody(), latency, reqMetrics);
				return response.getBody().getSentiment();
			}
		} catch (Exception e) {
			throw new Exception("Error occured while analysing the request:" + e.getMessage());
		}
		return null;
	}

	private void addMetrics(InferenceResponse response, long latency, RequestIDMetrics reqMetrics) {
		logger.info("Adding inference metrics to the dashboard.");
		metrics.updateMetrics(latency, response.getFeedbackScore(), response.getAccuracy(), response.getInferenceTime(),
				reqMetrics);
	}

}
